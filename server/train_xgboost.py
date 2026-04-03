"""
Train route-specific XGBoost ETA models using real BusLog history plus synthetic augmentation.
Run: python train_xgboost.py --route 72
"""

import argparse
import json
import logging
import os

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sqlalchemy import func

from app import app, get_current_stop_context
from generate_synthetic_data import FEATURE_COLUMNS, build_synthetic_training_dataframe
from models import BusLog, Route, RouteStop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transight")

MIN_REAL_SAMPLES = 50
DEFAULT_SYNTHETIC_ROWS = 4000
LEGACY_ROUTE_72_MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_eta_model.joblib")
LEGACY_ROUTE_72_METRICS_PATH = os.path.join(os.path.dirname(__file__), "xgboost_eta_metrics.json")


def normalize_route_name(route_name):
    """Normalize a route name for case-insensitive lookups and filenames."""
    return (route_name or "").strip().lower()


def get_model_path(route_name):
    """Return the route-specific model artifact path."""
    normalized = normalize_route_name(route_name)
    return os.path.join(os.path.dirname(__file__), f"xgboost_eta_model_{normalized}.joblib")


def get_metrics_path(route_name):
    """Return the route-specific metrics artifact path."""
    normalized = normalize_route_name(route_name)
    return os.path.join(os.path.dirname(__file__), f"xgboost_eta_metrics_{normalized}.json")


def collect_real_training_data(route_name):
    """Collect real BusLog rows for one route_name across both directions."""
    normalized_route = normalize_route_name(route_name)

    with app.app_context():
        logs = (
            BusLog.query
            .join(Route, BusLog.route_id == Route.id)
            .filter(func.lower(Route.route_name) == normalized_route)
            .filter(BusLog.predicted_eta.isnot(None))
            .filter(BusLog.bus_lat.isnot(None))
            .filter(BusLog.bus_lng.isnot(None))
            .order_by(BusLog.timestamp.asc())
            .all()
        )

        if len(logs) < MIN_REAL_SAMPLES:
            raise ValueError(
                f"Route {route_name} only has {len(logs)} usable real BusLog row(s). "
                f"Need at least {MIN_REAL_SAMPLES} before augmentation."
            )

        route_stops_cache = {}
        data = []
        directions = set()

        for log in logs:
            route = log.route
            if route is None:
                continue

            directions.add(route.direction)
            route_stops = route_stops_cache.get(route.id)
            if route_stops is None:
                route_stops = (
                    RouteStop.query
                    .filter_by(route_id=route.id)
                    .order_by(RouteStop.sequence)
                    .all()
                )
                route_stops_cache[route.id] = route_stops

            if not route_stops:
                continue

            current_stop_seq, _, _ = get_current_stop_context(route_stops, log.bus_lat, log.bus_lng)
            total_stops = route.total_stops or len(route_stops)
            remaining_stops = max(total_stops - current_stop_seq - 1, 0)
            progress_ratio = current_stop_seq / float(max(total_stops - 1, 1))

            data.append({
                "route_name": route.route_name,
                "direction": route.direction,
                "source": "real",
                "passenger_count": log.passenger_count or 0,
                "traffic_delay": log.traffic_delay or 0.0,
                "hour": log.timestamp.hour if log.timestamp else 12,
                "day_of_week": log.timestamp.weekday() if log.timestamp else 0,
                "current_stop_sequence": current_stop_seq,
                "remaining_stops": remaining_stops,
                "total_stops": total_stops,
                "progress_ratio": progress_ratio,
                "predicted_eta": log.predicted_eta,
            })

    df = pd.DataFrame(data)
    if len(df) < MIN_REAL_SAMPLES:
        raise ValueError(
            f"Route {route_name} only produced {len(df)} usable feature row(s) after stop matching. "
            f"Need at least {MIN_REAL_SAMPLES} before augmentation."
        )

    logger.info(
        "[Train] Collected %s real BusLog sample(s) for route %s across %s direction(s)",
        len(df),
        route_name,
        len(directions),
    )
    return df


def build_training_dataframe(route_name, synthetic_rows=DEFAULT_SYNTHETIC_ROWS, seed=42):
    """Combine real route-filtered BusLog history with synthetic augmentation."""
    real_df = collect_real_training_data(route_name)
    synthetic_df = build_synthetic_training_dataframe(
        route_name=route_name,
        num_samples=synthetic_rows,
        seed=seed,
    )
    combined = pd.concat([real_df, synthetic_df], ignore_index=True)
    logger.info(
        "[Train] Combined training dataset for route %s: %s real + %s synthetic = %s total",
        route_name,
        len(real_df),
        len(synthetic_df),
        len(combined),
    )
    return combined, real_df, synthetic_df


def train_model(df, route_name, metrics_path=None):
    """Train and save the route-specific XGBoost regression model."""
    X = df[FEATURE_COLUMNS]
    y = df["predicted_eta"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    logger.info("[Train] Training XGBoost model for route %s...", route_name)
    model = xgb.XGBRegressor(
        n_estimators=140,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = mse ** 0.5

    model_path = get_model_path(route_name)
    joblib.dump(model, model_path)
    logger.info("[Train] Saved model for route %s to %s", route_name, model_path)

    if normalize_route_name(route_name) == "72":
        joblib.dump(model, LEGACY_ROUTE_72_MODEL_PATH)
        logger.info("[Train] Refreshed legacy Route 72 model at %s", LEGACY_ROUTE_72_MODEL_PATH)

    source_counts = df["source"].value_counts().to_dict() if "source" in df.columns else {}
    metrics = {
        "route_name": route_name,
        "input_rows": len(df),
        "real_samples": int(source_counts.get("real", 0)),
        "synthetic_samples": int(source_counts.get("synthetic", 0)),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "mae_minutes": round(float(mae), 4),
        "rmse_minutes": round(float(rmse), 4),
        "feature_columns": FEATURE_COLUMNS,
        "feature_importance": {
            feature: round(float(importance), 6)
            for feature, importance in zip(FEATURE_COLUMNS, model.feature_importances_)
        },
        "model_path": model_path,
    }

    metrics_path = metrics_path or get_metrics_path(route_name)
    with open(metrics_path, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
    logger.info("[Train] Saved metrics for route %s to %s", route_name, metrics_path)

    if normalize_route_name(route_name) == "72":
        legacy_metrics = dict(metrics)
        legacy_metrics["model_path"] = LEGACY_ROUTE_72_MODEL_PATH
        with open(LEGACY_ROUTE_72_METRICS_PATH, "w", encoding="utf-8") as handle:
            json.dump(legacy_metrics, handle, indent=2)
        logger.info(
            "[Train] Refreshed legacy Route 72 metrics at %s",
            LEGACY_ROUTE_72_METRICS_PATH,
        )

    logger.info("[Train] Route %s performance:", route_name)
    logger.info("  Training samples: %s", len(X_train))
    logger.info("  Test samples: %s", len(X_test))
    logger.info("  MAE: %.2f minutes", mae)
    logger.info("  RMSE: %.2f minutes", rmse)
    logger.info("[Train] Feature importance:")
    for feature, importance in zip(FEATURE_COLUMNS, model.feature_importances_):
        logger.info("  %s: %.3f", feature, importance)

    return model, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train a route-specific XGBoost ETA model using real BusLog history plus synthetic augmentation."
    )
    parser.add_argument(
        "--route",
        required=True,
        help="Route short name to train, for example 72 or A1.",
    )
    parser.add_argument(
        "--synthetic-rows",
        type=int,
        default=DEFAULT_SYNTHETIC_ROWS,
        help=f"Number of synthetic rows to add on top of real BusLog data (default: {DEFAULT_SYNTHETIC_ROWS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for repeatable synthetic augmentation.",
    )
    parser.add_argument(
        "--metrics-json",
        default=None,
        help="Optional path for evaluation metadata JSON. Defaults to the route-specific metrics file.",
    )
    args = parser.parse_args()

    logger.info("=== XGBoost ETA Model Training ===")
    logger.info("[Train] Route target: %s", args.route)

    try:
        dataframe, real_df, synthetic_df = build_training_dataframe(
            route_name=args.route,
            synthetic_rows=args.synthetic_rows,
            seed=args.seed,
        )
    except ValueError as exc:
        logger.error("[Train] %s", exc)
        raise SystemExit(1) from exc

    model, metrics = train_model(
        dataframe,
        route_name=args.route,
        metrics_path=args.metrics_json,
    )

    logger.info("[Train] Training complete for route %s", args.route)
    logger.info("[Train] Real rows used: %s", len(real_df))
    logger.info("[Train] Synthetic rows used: %s", len(synthetic_df))
    logger.info("[Train] Model artifact: %s", metrics["model_path"])
    logger.info("[Train] Verify the running API now reports eta_method=xgboost for this route.")
