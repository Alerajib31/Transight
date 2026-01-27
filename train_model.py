import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

print("🧠 TRAINING XGBOOST MODEL...")

# 1. Load Data
df = pd.read_csv("historical_bus_data.csv")

# 2. Split into Features (X) and Target (y)
# We want to predict 'actual_arrival_time' based on the other columns
X = df[["traffic_delay", "crowd_count", "is_raining"]]
y = df["actual_arrival_time"]

# 3. Split into Train (80%) and Test (20%) sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Initialize and Train XGBoost
model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5)
model.fit(X_train, y_train)

# 5. Evaluate (Check how smart it is)
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

print(f"✅ MODEL TRAINED!")
print(f"   Accuracy Check: On average, the prediction is off by only {round(mae, 2)} minutes.")

# 6. Save the Brain
model.save_model("bus_prediction_model.json")
print("💾 Model saved to 'bus_prediction_model.json'")