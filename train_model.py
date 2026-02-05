"""
Transight ML Model Training Script
Trains XGBoost model for arrival time prediction using:
- traffic_delay: Real-time traffic from TomTom API
- crowd_count: Computer vision detection from sensors
- is_raining: Weather condition flag

Target: actual_arrival_time (minutes)
"""

import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import os

print("🧠 TRAINING TRANSIGHT PREDICTION MODEL...")
print("=" * 50)

# Check if historical data exists, if not create sample training data
data_file = "historical_bus_data.csv"

if not os.path.exists(data_file):
    print(f"⚠️  {data_file} not found. Creating sample training data...")
    
    # Create sample data that simulates real-world scenarios
    # This represents historical patterns for training
    import random
    
    data = []
    random.seed(42)
    
    for _ in range(2000):
        # Simulate realistic traffic conditions (0-30 min delay)
        traffic = round(random.uniform(0, 25), 1)
        
        # Simulate crowd count (0-20 people)
        crowd = random.randint(0, 20)
        
        # Rain flag (20% chance)
        raining = random.random() < 0.2
        
        # Calculate actual arrival time based on formula:
        # base + traffic + (crowd * dwell_time) + rain_penalty + noise
        dwell_time = (crowd * 4) / 60  # 4 seconds per person -> minutes
        rain_penalty = 2 if raining else 0
        noise = random.uniform(-1.0, 1.0)
        
        actual_arrival = traffic + dwell_time + rain_penalty + noise
        actual_arrival = max(0, round(actual_arrival, 2))  # Ensure non-negative
        
        data.append([traffic, crowd, int(raining), actual_arrival])
    
    df = pd.DataFrame(data, columns=["traffic_delay", "crowd_count", "is_raining", "actual_arrival_time"])
    df.to_csv(data_file, index=False)
    print(f"✅ Sample training data saved to {data_file}")
else:
    print(f"📊 Loading existing training data from {data_file}")

# 1. Load Data
df = pd.read_csv(data_file)
print(f"📈 Training samples: {len(df)}")

# 2. Split into Features (X) and Target (y)
# Features match the production system:
# - traffic_delay: From TomTom API (real-time)
# - crowd_count: From CV sensor (real-time)
# - is_raining: Weather flag (could be from weather API)
X = df[["traffic_delay", "crowd_count", "is_raining"]]
y = df["actual_arrival_time"]

# 3. Split into Train (80%) and Test (20%) sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Initialize and Train XGBoost
# Parameters tuned for transit prediction (small dataset, need generalization)
model = XGBRegressor(
    n_estimators=100,      # Number of trees
    learning_rate=0.1,     # Step size shrinkage
    max_depth=5,           # Maximum tree depth
    subsample=0.8,         # Subsample ratio of training instances
    colsample_bytree=0.8,  # Subsample ratio of columns
    objective='reg:squarederror',  # Regression task
    random_state=42
)

print("🏋️  Training model...")
model.fit(X_train, y_train)

# 5. Evaluate Model
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

print("=" * 50)
print(f"✅ MODEL TRAINING COMPLETE!")
print(f"   Mean Absolute Error: {round(mae, 2)} minutes")
print(f"   Model will predict arrival delays within ~{round(mae)} min on average")

# Feature importance
feature_importance = model.feature_importances_
print("\n📊 Feature Importance:")
for name, importance in zip(X.columns, feature_importance):
    print(f"   - {name}: {round(importance * 100, 1)}%")

# 6. Save the Model
model_path = "bus_prediction_model.json"
model.save_model(model_path)
print(f"\n💾 Model saved to '{model_path}'")

# 7. Test prediction with sample inputs
print("\n🧪 Sample Predictions:")
test_cases = [
    {"traffic_delay": 5, "crowd_count": 3, "is_raining": 0, "scenario": "Light traffic, small crowd"},
    {"traffic_delay": 15, "crowd_count": 12, "is_raining": 1, "scenario": "Heavy traffic, big crowd, raining"},
    {"traffic_delay": 0, "crowd_count": 0, "is_raining": 0, "scenario": "No delays, empty stop"},
]

for case in test_cases:
    features = pd.DataFrame([{
        "traffic_delay": case["traffic_delay"],
        "crowd_count": case["crowd_count"],
        "is_raining": case["is_raining"]
    }])
    pred = model.predict(features)[0]
    print(f"   {case['scenario']}: {round(pred, 1)} min delay")

print("\n🚀 Ready for production use!")
