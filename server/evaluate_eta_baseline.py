"""
Evaluate the trained XGBoost ETA model against a naive timetable + GPS baseline.

This quantifies the project's core claim: that fusing live signals (traffic,
crowd, stop progress) through an ML model predicts arrival time more accurately
than the timetable-and-GPS approach it aims to improve on.

Method
------
- Build a fresh synthetic test set the model never saw during training (a
  different random seed to the training run), where each row's target ETA is an
  independent formula that accounts for traffic and crowding.
- BASELINE (timetable + GPS): typical trip duration scaled by the GPS-derived
  fraction of the route still to travel. It has no access to live traffic or
  crowd, mirroring a classic timetable estimate.
- MODEL (XGBoost): predicts from all eight fused features.
- Score both with MAE and RMSE in minutes against the same target, and report
  the improvement.

Limitation to state openly in the viva: the target is a fused ETA estimate, not
observed real-world arrival times (which the system does not yet record). So
this measures how much the fused ML model improves on a timetable/GPS baseline,
not absolute real-world accuracy.

Run: python evaluate_eta_baseline.py --route 72
"""

import argparse
import json
import logging
import os

import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import func

from app import app
from generate_synthetic_data import (
    FEATURE_COLUMNS,
    build_synthetic_training_dataframe,
    normalize_route_name,
)
from models import Route
from train_xgboost import get_model_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transight")

# Different seed to the training run (train_xgboost.py uses seed=42) so these
# rows are unseen by the model.
DEFAULT_TEST_SEED = 99
DEFAULT_TEST_ROWS = 1500


def get_typical_durations(route_name: str) -> dict:
    """Map each direction of a route to its timetable typical duration (minutes)."""
    normalized = normalize_route_name(route_name)
    durations: dict[str, float] = {}
    with app.app_context():
        routes = (
            Route.query
            .filter(func.lower(Route.route_name) == normalized)
            .all()
        )
        for route in routes:
            durations[route.direction] = route.typical_duration_min
    return durations


def baseline_eta_minutes(row, durations: dict) -> float:
    """
    Naive timetable + GPS ETA: typical trip duration (timetable) scaled by the
    fraction of the route still to go (GPS-derived progress). No traffic/crowd.
    """
    typical = durations.get(row["direction"])
    if typical is None:
        # Same fallback the synthetic generator uses when a route lacks a timetable.
        typical = max(20.0, (row["total_stops"] or 0) * 1.8)
    remaining_fraction = max(0.0, 1.0 - row["progress_ratio"])
    return typical * remaining_fraction


def evaluate(route_name: str, test_rows: int, seed: int):
    """Score the model and the baseline on a fresh synthetic test set."""
    model_path = get_model_path(route_name)
    if not os.path.exists(model_path):
        raise SystemExit(
            f"No trained model for route {route_name} at {model_path}. "
            f"Train it first: python train_xgboost.py --route {route_name}"
        )
    model = joblib.load(model_path)

    test_df = build_synthetic_training_dataframe(
        route_name=route_name,
        num_samples=test_rows,
        seed=seed,
    )
    if test_df.empty:
        raise SystemExit(f"No test samples generated for route {route_name}.")

    durations = get_typical_durations(route_name)

    y_true = test_df["predicted_eta"].tolist()
    y_model = model.predict(test_df[FEATURE_COLUMNS]).tolist()
    y_baseline = [baseline_eta_minutes(row, durations) for _, row in test_df.iterrows()]

    model_mae = mean_absolute_error(y_true, y_model)
    model_rmse = mean_squared_error(y_true, y_model) ** 0.5
    baseline_mae = mean_absolute_error(y_true, y_baseline)
    baseline_rmse = mean_squared_error(y_true, y_baseline) ** 0.5

    mae_improvement_pct = (
        (baseline_mae - model_mae) / baseline_mae * 100.0 if baseline_mae else 0.0
    )
    rmse_improvement_pct = (
        (baseline_rmse - model_rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    )

    return {
        "route_name": route_name,
        "test_samples": len(test_df),
        "test_seed": seed,
        "baseline_method": "timetable_typical_duration_x_gps_progress",
        "baseline_mae_minutes": round(float(baseline_mae), 3),
        "baseline_rmse_minutes": round(float(baseline_rmse), 3),
        "xgboost_mae_minutes": round(float(model_mae), 3),
        "xgboost_rmse_minutes": round(float(model_rmse), 3),
        "mae_improvement_pct": round(float(mae_improvement_pct), 1),
        "rmse_improvement_pct": round(float(rmse_improvement_pct), 1),
    }


def print_report(result: dict) -> None:
    """Print a viva-friendly comparison table."""
    print("\n" + "=" * 60)
    print(f"  ETA ACCURACY: XGBoost vs Timetable+GPS baseline — Route {result['route_name']}")
    print("=" * 60)
    print(f"  Test samples (unseen, seed={result['test_seed']}): {result['test_samples']}")
    print("-" * 60)
    print(f"  {'Method':<28}{'MAE (min)':>14}{'RMSE (min)':>16}")
    print("-" * 60)
    print(
        f"  {'Timetable + GPS baseline':<28}"
        f"{result['baseline_mae_minutes']:>14}"
        f"{result['baseline_rmse_minutes']:>16}"
    )
    print(
        f"  {'XGBoost (fused signals)':<28}"
        f"{result['xgboost_mae_minutes']:>14}"
        f"{result['xgboost_rmse_minutes']:>16}"
    )
    print("-" * 60)
    print(
        f"  Improvement: MAE -{result['mae_improvement_pct']}%   "
        f"RMSE -{result['rmse_improvement_pct']}%"
    )
    print("=" * 60)
    print(
        "  Interpretation: the XGBoost model reduces mean absolute error by\n"
        f"  {result['mae_improvement_pct']}% versus a timetable/GPS-only estimate, because it\n"
        "  can see live traffic and crowding that the baseline cannot.\n"
        "  Note: target is a fused ETA estimate, not observed arrivals.\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare the XGBoost ETA model against a timetable+GPS baseline."
    )
    parser.add_argument(
        "--route",
        required=True,
        help="Route short name to evaluate, for example 72 or A1.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_TEST_ROWS,
        help=f"Number of unseen test samples to generate (default: {DEFAULT_TEST_ROWS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_TEST_SEED,
        help=f"Random seed for the test set, distinct from training (default: {DEFAULT_TEST_SEED}).",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the comparison result as JSON.",
    )
    args = parser.parse_args()

    outcome = evaluate(args.route, test_rows=args.rows, seed=args.seed)
    print_report(outcome)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(outcome, handle, indent=2)
        logger.info("[Evaluate] Wrote comparison to %s", args.json_out)
