# ML Module

Project: **ScholarPulse** — academic performance monitoring and institutional analytics

## Models

### Model 1 — Student Performance Prediction

- **Type:** Regression
- **Algorithm:** `HistGradientBoostingRegressor` (sklearn `Pipeline`)
- **Artifact:** `models/model_1/performance_model.pkl`
- **Output:** Predicted final grade (`G3`)

### Model 2 — Student Pass/Fail Prediction

- **Type:** Binary classification
- **Algorithm:** `LogisticRegression` (sklearn `Pipeline`)
- **Artifact:** `models/model_2/pass_fail_model.pkl`
- **Output:** `PASS` / `FAIL` with probabilities

### Model 3 — Student At-Risk Detection / Risk Assessment

- **Type:** Rule-based weighted scoring engine (not ML)
- **Configuration:** `models/model_3/risk_engine_config.json`
- **Output:** Risk score (0–100), risk level, indicators

## Purpose

This folder contains training notebooks, trained model artifacts, inference code, and documentation for the three academic intelligence components. It is designed for integration with the FastAPI backend.

**Authoritative documentation:** [`ml/docs/`](docs/README.md). Root-level `docs/ml-pipeline.md` describes an earlier planned pipeline and may not match this implementation.

## Setup

```bash
cd ml
uv sync
```

**Important:** Model 1 and Model 2 `.pkl` files were trained with **scikit-learn 1.6.1**. The project pins this version in `pyproject.toml`. Loading with a different sklearn version may fail.

## Folder Structure

```
ml/
├── README.md
├── requirements.txt
├── pyproject.toml
├── docs/                 # Model and pipeline documentation
├── notebooks/
│   ├── model_1/performance_model.ipynb
│   ├── model_2/pass_fail_model.ipynb
│   └── model_3/risk_model.ipynb
├── models/
│   ├── model_1/performance_model.pkl
│   ├── model_2/pass_fail_model.pkl
│   └── model_3/risk_engine_config.json
├── src/                  # Inference code
├── data/raw/             # UCI student-mat.csv
└── tests/
```

## Dataset

The current Model 1 and Model 2 artifacts are trained on the simulated CBCS datasets in `university_data/`. Some legacy notebooks and documentation also reference the UCI Student Performance Dataset (`data/raw/student-mat.csv`); that dataset is not the input to the current CBCS training script.

## Dataset sizes

The current training datasets are generated from the simulated CBCS course results in `university_data/`:

| Dataset | Rows |
|---------|-----:|
| `model1_regression_dataset.csv` | 269,683 |
| `model2_pass_fail_dataset.csv` | 347,744 |

Model 1 records CA_MID_END and CA_END course results when an end-term mark is available (including NON_CREDIT CA_END courses). Model 2 records every credit-bearing course result, including LAB and PROJECT courses assessed without an end-term exam. Those additional credit-bearing course results make Model 2 larger; it is not caused by repeated attempts.

## How to retrain

From the repository root, run:

```bash
cd backend
RUN_MODEL_RETRAIN=1 uv run python ../ml/models/student_results_dataset_and_models_training.py
```

The retraining process uses `DATA_DIR` (default `university_data`) and `MODEL_DIR` (default `ml/models`), resolved relative to the repository root unless set to absolute paths. `RUN_SIMULATION` defaults to `false`, so the committed CSV datasets are not regenerated or overwritten. Allow approximately **5–10 minutes**, depending on available CPU and memory.

The command requires scikit-learn 1.6.1 and writes:

- `ml/models/model1_endterm_histgradientboosting.pkl`
- `ml/models/model2_pass_fail_histgradientboosting.pkl`
- `ml/models/model1_metrics.json`
- `ml/models/model2_metrics.json`
- `ml/models/model1_feature_importance.csv`

Both models use student-level splits so a student's course rows cannot occur in both training and test sets. Model 1 uses `GroupShuffleSplit`; Model 2 uses the first fold of a shuffled, seeded five-fold `StratifiedGroupKFold`.

## Frozen metrics

The following table compares the previous row-level evaluation with the new student-level evaluation. The Model 2 before/after rows use each model's respective test set; accuracy is accompanied by the always-PASS baseline to make the class imbalance visible.

| Model / metric | Before (row-level) | After (student-level) |
|----------------|-------------------:|----------------------:|
| Model 1 test rows | 53,937 | 53,971 |
| Model 1 MAE | 5.6312 | 5.6549 |
| Model 1 RMSE | 7.0712 | 7.0895 |
| Model 1 R² | 0.7636 | 0.7574 |
| Model 2 test rows | 69,549 | 69,585 |
| Model 2 accuracy | 0.9533 | 0.9595 |
| Model 2 always-PASS accuracy | 0.9908 | 0.9919 |
| Model 2 FAIL precision | 0.1614 | 0.1606 |
| Model 2 FAIL recall | 0.9673 | 0.9519 |
| Model 2 FAIL F1 | 0.2767 | 0.2748 |
| Model 2 ROC-AUC | 0.9906 | 0.9912 |
| Model 2 PR-AUC | Not recorded | 0.5849 |

## CA-only variants

The CA-only pipelines use the same student-level train/test split, preprocessing, estimator hyperparameters, and default prediction decisions as the full models, but omit `MID_mark`. They retain the original CSV representation of missing prior GPA values: semester-1 `previous_sgpa` and `previous_cgpa` values are NaN, which the pipeline's numeric median imputer handles.

| Artifact | Input columns, in required order |
|----------|----------------------------------|
| `model1_endterm_ca_only_histgradientboosting.pkl` | `CA_mark`, `attendance_percentage`, `study_hours_per_week`, `assignment_completion_pct`, `previous_sgpa`, `previous_cgpa`, `backlog_count`, `course_credits`, `course_type`, `branch`, `semester` |
| `model2_pass_fail_ca_only_histgradientboosting.pkl` | `CA_mark`, `attendance_percentage`, `study_hours_per_week`, `assignment_completion_pct`, `previous_sgpa`, `previous_cgpa`, `backlog_count`, `course_credits`, `branch`, `semester` |

Metrics and the held-out comparison against the full models are in `model1_ca_only_metrics.json` and `model2_ca_only_metrics.json`. To train only the CA-only variants from the repository root, run:

```bash
cd backend
RUN_CA_ONLY_RETRAIN=1 uv run python ../ml/models/student_results_dataset_and_models_training.py
```

| Metric | Model 1 full | Model 1 CA-only | Model 2 full | Model 2 CA-only |
|--------|-------------:|---------------:|-------------:|---------------:|
| MAE | 5.6549 | 5.9428 | — | — |
| RMSE | 7.0895 | 7.4585 | — | — |
| R² | 0.7574 | 0.7315 | — | — |
| FAIL recall | — | — | 0.9519 | 0.9340 |
| FAIL precision | — | — | 0.1606 | 0.1452 |
| PR-AUC | — | — | 0.5849 | 0.5073 |
| ROC-AUC | — | — | 0.9912 | 0.9888 |
| FAIL base rate | — | — | 0.0081 | 0.0081 |

## Inference

```python
from src.model_1.predictor import predict_performance
from src.model_2.predictor import predict_pass_fail
from src.model_3.risk_engine import assess_student_risk

# Model 1 — 32 UCI features (see src/common/features.py)
result = predict_performance(student_dict)
# {"predicted_g3": 13.7}

# Model 2 — same 32 features
result = predict_pass_fail(student_dict)
# {"prediction": "PASS", "pass_probability": 0.99, "fail_probability": 0.01}

# Model 3 — 5 risk fields
result = assess_student_risk({
    "absences": 6, "G1": 10, "G2": 9, "failures": 1, "studytime": 2
})
# {"risk_score": 47.5, "risk_level": "MEDIUM", "risk_indicators": [...], ...}
```

See [`docs/inference.md`](docs/inference.md) for input/output contracts and backend integration notes.

## Tests

```bash
uv run pytest tests/ -v
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ml_architecture.md](docs/ml_architecture.md) | Architecture overview |
| [docs/models_overview.md](docs/models_overview.md) | Component comparison |
| [docs/model_1_performance.md](docs/model_1_performance.md) | Model 1 details |
| [docs/model_2_pass_fail.md](docs/model_2_pass_fail.md) | Model 2 details |
| [docs/model_3_risk_assessment.md](docs/model_3_risk_assessment.md) | Model 3 risk engine |
| [docs/data_pipeline.md](docs/data_pipeline.md) | Data loading and preprocessing |
| [docs/model_evaluation.md](docs/model_evaluation.md) | Evaluation metrics |
| [docs/inference.md](docs/inference.md) | Inference API |

## Feature Importance, Ablation, and Threshold-Cost Analysis

The analyses use the held-out student-level splits (Model 1: 53,971 rows / 2,000 students; Model 2: 69,585 rows / 1,995 students / 561 FAILs). Permutation importance uses all held-out rows, five repeats, and seed 42. Model 1 importance is the increase in MAE; Model 2 importance is the decrease in average precision for FAIL.

### Top features by permutation importance

| Rank | Model 1 feature | MAE increase |
|---:|---|---:|
| 1 | `CA_mark` | 5.304304 |
| 2 | `MID_mark` | 1.262776 |
| 3 | `previous_cgpa` | 0.444998 |
| 4 | `study_hours_per_week` | 0.028512 |
| 5 | `backlog_count` | 0.023841 |

| Rank | Model 2 feature | FAIL average-precision decrease |
|---:|---|---:|
| 1 | `backlog_count` | 0.549465 |
| 2 | `MID_mark` | 0.191971 |
| 3 | `CA_mark` | 0.182226 |
| 4 | `previous_cgpa` | 0.089642 |
| 5 | `course_credits` | 0.062319 |

All features and standard deviations are recorded in `models/model1_feature_importance.csv` and `models/model2_feature_importance.csv`.

### Feature-group ablation

Fresh clones of the full pipelines were fit on the training rows and evaluated on the same held-out test rows. Deltas are relative to Full.

| Model 1 configuration | MAE (Δ) | RMSE (Δ) | R² (Δ) |
|---|---:|---:|---:|
| Full model | 5.654861 (0.000000) | 7.089512 (0.000000) | 0.757390 (0.000000) |
| Drop `MID_mark` only | 5.942767 (+0.287906) | 7.458517 (+0.369004) | 0.731478 (-0.025913) |
| Drop all Assessments | 8.345810 (+2.690949) | 10.456414 (+3.366901) | 0.472234 (-0.285156) |
| Drop Engagement / Behavioral | 5.661289 (+0.006428) | 7.096271 (+0.006758) | 0.756927 (-0.000463) |
| Drop Prior Academic History | 5.827282 (+0.172421) | 7.301853 (+0.212341) | 0.742639 (-0.014751) |

| Model 2 configuration | FAIL Recall (Δ) | FAIL Precision (Δ) | PR-AUC (Δ) | ROC-AUC (Δ) |
|---|---:|---:|---:|---:|
| Full model | 0.951872 (0.000000) | 0.160602 (0.000000) | 0.584915 (0.000000) | 0.991248 (0.000000) |
| Drop `MID_mark` only | 0.934046 (-0.017825) | 0.145193 (-0.015409) | 0.507328 (-0.077587) | 0.988774 (-0.002475) |
| Drop all Assessments | 0.957219 (+0.005348) | 0.109257 (-0.051344) | 0.291416 (-0.293499) | 0.982110 (-0.009138) |
| Drop Engagement / Behavioral | 0.960784 (+0.008913) | 0.161136 (+0.000535) | 0.605520 (+0.020605) | 0.991798 (+0.000550) |
| Drop Prior Academic History | 0.698752 (-0.253119) | 0.030022 (-0.130579) | 0.354163 (-0.230752) | 0.876645 (-0.114603) |

### Model 2 threshold-cost sweep

Predictions are flagged when `p(FAIL) >= threshold`. FP/TP is the false-alerts-per-true-fail ratio; flagged percentage uses all 69,585 test enrollments.

| Model | Threshold | TP | FP | FN | FAIL Recall | FAIL Precision | FP / TP | Flagged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full | 0.10 | 557 | 4,740 | 4 | 0.9929 | 0.1052 | 8.510 | 7.612% |
| Full | 0.20 | 553 | 4,076 | 8 | 0.9857 | 0.1195 | 7.371 | 6.652% |
| Full | 0.30 | 547 | 3,590 | 14 | 0.9750 | 0.1322 | 6.563 | 5.945% |
| Full | 0.40 | 542 | 3,169 | 19 | 0.9661 | 0.1461 | 5.847 | 5.333% |
| Full | 0.50 | 534 | 2,791 | 27 | 0.9519 | 0.1606 | 5.227 | 4.778% |
| Full | 0.60 | 526 | 2,441 | 35 | 0.9376 | 0.1773 | 4.641 | 4.264% |
| Full | 0.70 | 517 | 2,030 | 44 | 0.9216 | 0.2030 | 3.926 | 3.660% |
| Full | 0.80 | 492 | 1,497 | 69 | 0.8770 | 0.2474 | 3.043 | 2.858% |
| CA-only | 0.10 | 556 | 5,148 | 5 | 0.9911 | 0.0975 | 9.259 | 8.197% |
| CA-only | 0.20 | 552 | 4,439 | 9 | 0.9840 | 0.1106 | 8.042 | 7.173% |
| CA-only | 0.30 | 548 | 3,942 | 13 | 0.9768 | 0.1220 | 7.193 | 6.453% |
| CA-only | 0.40 | 540 | 3,488 | 21 | 0.9626 | 0.1341 | 6.459 | 5.789% |
| CA-only | 0.50 | 524 | 3,085 | 37 | 0.9340 | 0.1452 | 5.887 | 5.186% |
| CA-only | 0.60 | 513 | 2,663 | 48 | 0.9144 | 0.1615 | 5.191 | 4.564% |
| CA-only | 0.70 | 497 | 2,164 | 64 | 0.8859 | 0.1868 | 4.354 | 3.824% |
| CA-only | 0.80 | 470 | 1,578 | 91 | 0.8378 | 0.2295 | 3.357 | 2.943% |

### Policy operating points

High-recall screening selects the sweep threshold meeting at least 90% recall with the fewest false alerts. No sweep threshold meets the 2.0% cap, so capacity-constrained thresholds use the lowest observed score still within the 1,391-enrollment limit.

| Model | Policy | Threshold | TP | FP | FN | FAIL Recall | FAIL Precision | Flagged |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Full | High-recall screening | 0.70 | 517 | 2,030 | 44 | 0.9216 | 0.2030 | 3.660% |
| CA-only | High-recall screening | 0.60 | 513 | 2,663 | 48 | 0.9144 | 0.1615 | 4.564% |
| Full | Capacity-constrained (≤2.0%) | 0.883089 | 442 | 949 | 119 | 0.7879 | 0.3178 | 1.999% |
| CA-only | Capacity-constrained (≤2.0%) | 0.886314 | 409 | 982 | 152 | 0.7291 | 0.2940 | 1.999% |

Complete tables and split/method details are in `models/ablation_and_threshold_analysis.json`.
