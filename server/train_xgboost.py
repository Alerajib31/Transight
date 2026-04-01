"""
Train XGBoost model for ETA prediction using historical BusLog data.
Run: python train_xgboost.py
"""

import os
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import logging

from app import app, get_current_stop_context
from models import BusLog, RouteStop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transight")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_eta_model.joblib")
FEATURE_COLUMNS = [
    "passenger_count",
    "traffic_delay",
    "hour",
    "day_of_week",
    "current_stop_sequence",
    "remaining_stops",
    "total_stops",
    "progress_ratio",
]


def collect_training_data():
    """Collect historical data from BusLog table."""
    with app.app_context():
        logs = BusLog.query.all()

        if len(logs) < 50:
            logger.warning(f"Only {len(logs)} records found. Need at least 50 for training.")
            logger.warning("Run generate_synthetic_data.py to create training data!")
            return None

        data = []
        for log in logs:
            route = log.route
            if route is None or log.bus_lat is None or log.bus_lng is None:
                continue

            route_stops = (RouteStop.query
                           .filter_by(route_id=route.id)
                           .order_by(RouteStop.sequence)
                           .all())
            if not route_stops:
                continue

            current_stop_seq, _, _ = get_current_stop_context(route_stops, log.bus_lat, log.bus_lng)
            total_stops = route.total_stops or len(route_stops)
            remaining_stops = max(total_stops - current_stop_seq - 1, 0)
            progress_ratio = current_stop_seq / float(max(total_stops - 1, 1))

            # Extract features
            data.append({
                'passenger_count': log.passenger_count,
                'traffic_delay': log.traffic_delay,
                'hour': log.timestamp.hour if log.timestamp else 12,
                'day_of_week': log.timestamp.weekday() if log.timestamp else 0,
                'current_stop_sequence': current_stop_seq,
                'remaining_stops': remaining_stops,
                'total_stops': total_stops,
                'progress_ratio': progress_ratio,
                'predicted_eta': log.predicted_eta,
            })

        df = pd.DataFrame(data)
        logger.info(f"Collected {len(df)} training samples")
        return df


def train_model(df):
    """Train XGBoost regression model."""

    # Features
    X = df[FEATURE_COLUMNS]
    y = df['predicted_eta']

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train XGBoost
    logger.info("Training XGBoost model...")
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective="reg:squarederror",
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = mse ** 0.5

    logger.info(f"\nModel Performance:")
    logger.info(f"  Training samples: {len(X_train)}")
    logger.info(f"  Test samples: {len(X_test)}")
    logger.info(f"  MAE: {mae:.2f} minutes")
    logger.info(f"  RMSE: {rmse:.2f} minutes")

    # Feature importance
    logger.info(f"\nFeature Importance:")
    for feat, imp in zip(FEATURE_COLUMNS, model.feature_importances_):
        logger.info(f"  {feat}: {imp:.3f}")

    # Save model
    joblib.dump(model, MODEL_PATH)
    logger.info(f"\nModel saved to {MODEL_PATH}")

    return model


if __name__ == "__main__":
    logger.info("=== XGBoost ETA Model Training ===\n")

    # Collect data
    df = collect_training_data()

    if df is None or df.empty:
        logger.error("Not enough data. Run: python generate_synthetic_data.py")
        exit(1)

    # Train model
    model = train_model(df)

    logger.info("\nTraining complete!")
    logger.info("Next steps:")
    logger.info("  1. Start the backend so it loads the refreshed xgboost_eta_model.joblib")
    logger.info("  2. Verify /api/status/1 and /api/routes/1/predictions return expected Route 72 data")
