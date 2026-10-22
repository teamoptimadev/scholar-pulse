"""Model 2 — Pass/fail prediction (HistGradientBoostingClassifier)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml.model_loader import model_loader

MODEL2_FEATURES = [
    "CA_mark",
    "MID_mark",
    "attendance_percentage",
    "study_hours_per_week",
    "assignment_completion_pct",
    "previous_sgpa",
    "previous_cgpa",
    "backlog_count",
    "course_credits",
    "branch",
    "semester",
]
MODEL2_CA_ONLY_FEATURES = [feature for feature in MODEL2_FEATURES if feature != "MID_mark"]

# Training labels: 0 = FAIL, 1 = PASS
_LABEL_MAP = {0: "FAIL", 1: "PASS"}


def predict_pass_fail(features: dict[str, Any]) -> dict[str, Any]:
    """Predict pass/fail outcome with probabilities."""
    if not model_loader.is_loaded:
        raise RuntimeError("ML models not loaded")

    has_mid_mark = features.get("MID_mark") is not None
    feature_names = MODEL2_FEATURES if has_mid_mark else MODEL2_CA_ONLY_FEATURES
    model = model_loader.pass_fail_model if has_mid_mark else model_loader.pass_fail_model_ca_only
    row = {f: features.get(f) for f in feature_names}
    df = pd.DataFrame([row])

    pred_class = int(model.predict(df)[0])
    proba = model.predict_proba(df)[0]

    classes = list(model.classes_)
    fail_idx = classes.index(0) if 0 in classes else 0
    pass_idx = classes.index(1) if 1 in classes else 1

    fail_prob = round(float(proba[fail_idx]), 4)
    pass_prob = round(float(proba[pass_idx]), 4)

    return {
        "prediction": _LABEL_MAP.get(pred_class, "FAIL"),
        "pass_probability": pass_prob,
        "fail_probability": fail_prob,
        "model_stage": "full" if has_mid_mark else "ca_only",
    }
