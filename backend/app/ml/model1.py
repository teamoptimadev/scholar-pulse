"""Model 1 — End-term performance prediction (HistGradientBoostingRegressor)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml.model_loader import model_loader

MODEL1_FEATURES = [
    "CA_mark",
    "MID_mark",
    "attendance_percentage",
    "study_hours_per_week",
    "assignment_completion_pct",
    "previous_sgpa",
    "previous_cgpa",
    "backlog_count",
    "course_credits",
    "course_type",
    "branch",
    "semester",
]
MODEL1_CA_ONLY_FEATURES = [feature for feature in MODEL1_FEATURES if feature != "MID_mark"]


def predict_performance(features: dict[str, Any]) -> dict[str, Any]:
    """Predict end-term marks with the full or CA-only model."""
    if not model_loader.is_loaded:
        raise RuntimeError("ML models not loaded")

    has_mid_mark = features.get("MID_mark") is not None
    feature_names = MODEL1_FEATURES if has_mid_mark else MODEL1_CA_ONLY_FEATURES
    model = model_loader.performance_model if has_mid_mark else model_loader.performance_model_ca_only
    row = {f: features.get(f) for f in feature_names}
    df = pd.DataFrame([row])
    raw = float(model.predict(df)[0])
    return {
        "predicted_end_marks": round(max(0.0, min(100.0, raw)), 2),
        "model_stage": "full" if has_mid_mark else "ca_only",
    }
