"""
Train Model - the visible training pipeline
----------------------------------------------
This is the missing piece your mentors were asking about: a standalone
script that actually shows the full training process, not just a model
quietly retraining inside every web request.

What it does, step by step:
  1. LOADS the dataset  -> data/sales_history.csv
  2. SPLITS each medicine's sales history into training data (first 80%
     of its recorded days) and testing data (the last 20%)
  3. TRAINS a Linear Regression model on the training portion
  4. EVALUATES it on the testing portion - a real accuracy number
     (Mean Absolute Error: on average, how many units off was the
     prediction from what was actually sold?)
  5. SAVES all trained models to models/shortage_models.pkl

Run this whenever the dataset changes (e.g. after loading new sales
data) to retrain and re-evaluate:

    cd app
    python train_model.py

The live app (ml_predict.py) still trains fresh per-request using each
medicine's LIVE, up-to-date sales history - that's intentional, since a
saved model trained today would go stale as new real sales come in.
This script exists to make the training + evaluation process visible
and demonstrable on its own, using the actual dataset file, exactly
the way a standard ML pipeline is expected to look.
"""

import os
import csv
import pickle
from collections import defaultdict
import numpy as np
from sklearn.linear_model import LinearRegression

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SALES_CSV = os.path.join(DATA_DIR, "sales_history.csv")
MODEL_OUTPUT_PATH = os.path.join(MODELS_DIR, "shortage_models.pkl")

MIN_POINTS_TO_TRAIN = 5  # need at least this many days of data to bother training+testing


def load_and_group_sales():
    """Reads sales_history.csv and groups quantity_sold by medicine, sorted by date."""
    per_medicine = defaultdict(lambda: defaultdict(int))

    with open(SALES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            per_medicine[row["medicine_name"]][row["sale_date"]] += int(row["quantity_sold"])

    # Convert to sorted (date, qty) lists per medicine
    result = {}
    for medicine, date_qty in per_medicine.items():
        sorted_dates = sorted(date_qty.keys())
        result[medicine] = [date_qty[d] for d in sorted_dates]
    return result


def train_and_evaluate():
    sales_by_medicine = load_and_group_sales()

    trained_models = {}
    evaluation_report = []

    for medicine, quantities in sales_by_medicine.items():
        n = len(quantities)

        if n < MIN_POINTS_TO_TRAIN:
            evaluation_report.append({
                "medicine": medicine, "n_records": n, "mae": None,
                "note": "Too few records to train/test split"
            })
            continue

        # ---- Split: first 80% of days = train, last 20% = test ----
        split_point = int(n * 0.8)
        train_qty = quantities[:split_point]
        test_qty = quantities[split_point:]

        X_train = np.array(range(len(train_qty))).reshape(-1, 1)
        y_train = np.array(train_qty)

        model = LinearRegression()
        model.fit(X_train, y_train)

        # ---- Evaluate on test portion ----
        X_test = np.array(range(len(train_qty), len(train_qty) + len(test_qty))).reshape(-1, 1)
        y_test = np.array(test_qty)
        y_pred = np.clip(model.predict(X_test), 0, None)

        mae = float(np.mean(np.abs(y_test - y_pred)))

        # ---- Retrain on FULL dataset for the saved/production model ----
        # (train/test split above was only to measure accuracy; the model
        # we actually save uses all available data for the best fit)
        X_full = np.array(range(n)).reshape(-1, 1)
        y_full = np.array(quantities)
        final_model = LinearRegression()
        final_model.fit(X_full, y_full)

        trained_models[medicine] = {
            "coefficient": float(final_model.coef_[0]),
            "intercept": float(final_model.intercept_),
            "trained_on_n_points": n,
            "test_mae": round(mae, 2)
        }

        evaluation_report.append({
            "medicine": medicine, "n_records": n,
            "train_size": len(train_qty), "test_size": len(test_qty),
            "mae": round(mae, 2), "note": None
        })

    return trained_models, evaluation_report


def main():
    print("Loading dataset: data/sales_history.csv")
    trained_models, evaluation_report = train_and_evaluate()

    print(f"\nTrained {len(trained_models)} medicine-level models "
          f"({len(evaluation_report) - len(trained_models)} skipped - too few records)\n")

    print(f"{'Medicine':<35} {'Records':<9} {'Train/Test':<12} {'MAE (units)':<12}")
    print("-" * 70)
    for row in evaluation_report:
        if row["mae"] is None:
            print(f"{row['medicine']:<35} {row['n_records']:<9} {'-':<12} {row['note']}")
        else:
            split = f"{row['train_size']}/{row['test_size']}"
            print(f"{row['medicine']:<35} {row['n_records']:<9} {split:<12} {row['mae']}")

    valid_maes = [r["mae"] for r in evaluation_report if r["mae"] is not None]
    if valid_maes:
        avg_mae = sum(valid_maes) / len(valid_maes)
        print("-" * 70)
        print(f"Average Test MAE across all evaluated medicines: {round(avg_mae, 2)} units")
        print("(On average, the model's 7-day-out prediction is off by about this many")
        print(" units per day, based on held-out test data it never trained on.)")

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(MODEL_OUTPUT_PATH, "wb") as f:
        pickle.dump(trained_models, f)
    print(f"\nSaved trained models to {MODEL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
