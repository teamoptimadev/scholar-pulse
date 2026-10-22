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
