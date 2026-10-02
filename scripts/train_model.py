"""
drone-detector/scripts/train_model.py
Train ML Classifier
===================

Tujuan:
- Melatih classifier ML untuk klasifikasi sinyal (drone / noise / unknown)
- Menggunakan feature tabular (bukan deep learning)
- Output model: models/classifier.pkl

Catatan penting:
- Script ini TIDAK dipanggil saat runtime
- ML classifier bersifat OPSIONAL
- Sistem tetap berjalan tanpa model ini
"""

import json
import pickle
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier


# ------------------------------------------------------------
# Config
# ------------------------------------------------------------

DEFAULT_FEATURES = [
    "peak_count",
    "mean_power",
    "max_power",
    "power_variance",
    "peak_mean_power",
    "peak_max_power",
]

MODEL_OUTPUT = Path("models/classifier.pkl")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def load_features(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    return pd.read_csv(csv_path)


def load_labels(labels_path: Path) -> dict:
    with open(labels_path, "r") as f:
        return json.load(f)


def prepare_dataset(df: pd.DataFrame, features: list):
    X = df[features]
    y = df["label"]
    return X, y


def train_model(X, y):
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X, y)
    return model


def save_model(model, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Train Drone Signal Classifier")
    parser.add_argument(
        "--features",
        default="data/exports/ml/features.csv",
        help="CSV file with extracted features",
    )
    parser.add_argument(
        "--labels",
        default="data/iq/labels.json",
        help="Auto/manual labels JSON",
    )
    parser.add_argument(
        "--output",
        default=str(MODEL_OUTPUT),
        help="Output classifier.pkl path",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.25,
        help="Test split ratio",
    )

    args = parser.parse_args()

    print("[*] Loading dataset...")
    df = load_features(Path(args.features))

    print("[*] Preparing features...")
    X, y = prepare_dataset(df, DEFAULT_FEATURES)

    print("[*] Train / Test split...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )

    print("[*] Training model...")
    model = train_model(X_train, y_train)

    print("[*] Evaluating model...")
    preds = model.predict(X_test)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, preds))

    print("\n=== Confusion Matrix ===")
    print(confusion_matrix(y_test, preds))

    print("[*] Saving model...")
    save_model(model, Path(args.output))

    print(f"[OK] Model saved → {args.output}")


if __name__ == "__main__":
    main()
