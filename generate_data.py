import pandas as pd
import random
import numpy as np

# CONFIGURATION
NUM_SAMPLES = 2000 # Generate 2,000 simulated bus arrivals

print("📊 GENERATING SYNTHETIC HISTORICAL DATASET...")

data = []

for _ in range(NUM_SAMPLES):
    # 1. Random Input: Traffic Delay (0 to 30 mins)
    traffic = round(random.uniform(0, 30), 1)
    
    # 2. Random Input: Crowd Count (0 to 50 people)
    crowd = random.randint(0, 50)
    
    # 3. Random Input: Weather (0=Clear, 1=Rain)
    rain = random.choice([0, 1])
    
    # --- THE HIDDEN "REALITY" FORMULA ---
    # We want the ML model to "discover" this relationship:
    # Base Time + Traffic + (Crowd * 4s) + Rain Penalty + Noise
    dwell_time = (crowd * 4.0) / 60.0 # Convert seconds to mins
    rain_penalty = 2.0 if rain == 1 else 0.0
    
    # The "Actual" arrival time (Label)
    # We add random noise (-1 to +1 min) because real life isn't perfect
    actual_arrival = traffic + dwell_time + rain_penalty + random.uniform(-1.0, 1.0)
    
    # Ensure no negative times
    actual_arrival = max(1.0, round(actual_arrival, 1))
    
    data.append([traffic, crowd, rain, actual_arrival])

# Save to CSV
df = pd.DataFrame(data, columns=["traffic_delay", "crowd_count", "is_raining", "actual_arrival_time"])
df.to_csv("historical_bus_data.csv", index=False)

print(f"✅ SUCCESS: Saved 'historical_bus_data.csv' with {NUM_SAMPLES} records.")
print(df.head())