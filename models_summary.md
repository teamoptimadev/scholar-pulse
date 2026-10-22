# Student Academic Intelligence - ML Models Summary

This document summarizes the three academic intelligence components developed for ScholarPulse. They use the synthetic CBCS university dataset in `university_data/` and the versioned artifacts in `ml/models/`.

---

# Model 1 - Student End-Term Mark Prediction

## Purpose

Model 1 predicts a student's end-term marks on a 0-100 scale.

### Question answered

> "What end-term mark is this student likely to achieve?"

## ML Problem

**Regression**

```text
Academic Information
        v
Performance Model
        v
Predicted End-Term Marks (0-100)
```

## Dataset

The training data is `university_data/model1_regression_dataset.csv`, with 269,683 rows. The train/test split has 215,712 training samples and 53,971 test samples, grouped by student with seed 42 (see `ml/models/model1_metrics.json`).

Target:

```text
TARGET_END_MARKS
```

Input features, matching `backend/app/ml/model1.py`:

```text
CA_mark
MID_mark
attendance_percentage
study_hours_per_week
assignment_completion_pct
previous_sgpa
previous_cgpa
backlog_count
course_credits
course_type
branch
semester
```

## Models Compared

The training comparison considered regression approaches, with HistGradientBoostingRegressor selected for the deployed artifact.

## Selected Model

```text
HistGradientBoostingRegressor
```

Evaluation metrics are taken directly from `ml/models/model1_metrics.json`:

| Metric | Value |
|---|---:|
| MAE | 5.65486118852561 |
| RMSE | 7.089512420739615 |
| R2 | 0.757390134321228 |

The baseline MAE from the training mean is 11.871468615094395 (see `ml/models/model1_metrics.json`).

## Model Artifact

```text
ml/models/model1_endterm_histgradientboosting.pkl
```

The backend loads the serialized scikit-learn model and returns `predicted_end_marks`, clamped to the 0-100 range.

---

# Model 2 - Student Pass/Fail Prediction

## Purpose

Model 2 predicts whether a student is likely to pass or fail and returns both class probabilities.

### Question answered

> "Is this student likely to pass or fail?"

## ML Problem

**Binary Classification**

```text
Academic Information
        v
Pass/Fail Classifier
        v
PASS / FAIL + probabilities
```

## Dataset

The training data is `university_data/model2_pass_fail_dataset.csv`, with 347,744 rows. It is a different row set from Model 1. The split has 278,159 training rows and 69,585 test rows across 1,995 test students, using StratifiedGroupKFold by student with seed 42 (see `ml/models/model2_metrics.json`).

Target:

```text
TARGET_PASS_FAIL
```

Input features, matching `backend/app/ml/model2.py`:

```text
CA_mark
MID_mark
attendance_percentage
study_hours_per_week
assignment_completion_pct
previous_sgpa
previous_cgpa
backlog_count
course_credits
branch
semester
```

## Selected Model

```text
HistGradientBoostingClassifier
```

It was selected for the highest FAIL recall and ROC-AUC among the evaluated models. Evaluation metrics are taken directly from `ml/models/model2_metrics.json`:

| Metric | Value |
|---|---:|
| Accuracy | 0.9595027664008048 |
| FAIL precision | 0.1606015037593985 |
| FAIL recall | 0.9518716577540107 |
| FAIL F1 | 0.2748327328872877 |
| ROC-AUC | 0.9912483616745048 |
| PR-AUC | 0.5849150073772301 |
| Precision lift | 19.920598287161756 |
| False alerts per true FAIL | 5.226591760299625 |
| Always-PASS accuracy | 0.991937917654667 |
| FAIL base rate | 0.008062082345333045 |

The test set contains 561 FAIL rows. At the default threshold, the confusion matrix is `[[534, 27], [2791, 66233]]` (see `ml/models/model2_metrics.json`).

## Output

```text
prediction: PASS or FAIL
pass_probability: probability from 0 to 1
fail_probability: probability from 0 to 1
```

The probabilities are model estimates, not guarantees. The threshold sweep and its precision/recall trade-offs are preserved in `ml/models/model2_metrics.json`.

## Model Artifact

```text
ml/models/model2_pass_fail_histgradientboosting.pkl
```

---

# Model 3 - Student At-Risk Detection

## Purpose

Model 3 identifies students who may require academic intervention. It is a transparent, weighted, rule-based risk engine rather than an ML classifier.

### Question answered

> "Which students currently need attention, and which indicators contribute most to that assessment?"

## Risk Engine Version

The policy is version 1.1 in `ml/models/model3_risk_engine_config.json`. The engine produces a score from 0 to 100 and classifies it as LOW, MEDIUM, or HIGH using the configured thresholds:

```text
LOW: 0-22
MEDIUM: greater than 22 through 38
HIGH: greater than 38
```

The weighted inputs are:

| Feature | Weight |
|---|---:|
| attendance_percentage | 0.2 |
| previous_cgpa | 0.2 |
| backlog_count | 0.2 |
| current_failed_courses | 0.15 |
| low_performance_course_count | 0.1 |
| study_hours_per_week | 0.05 |
| assignment_completion_percentage | 0.05 |
| performance_trend | 0.05 |

Missing-data rules are explicit. History indicators contribute 0 when missing; behaviour and prior-attainment indicators contribute half of their weight. With every input missing, the score is 25.0 and the level is MEDIUM.

## Explainable Output

Risk responses include:

```text
risk_score
risk_level
data_completeness: 0 to 1
top_factors: up to 3 items
```

Each top factor contains `feature`, `contribution`, `value`, and `is_missing`. Only positive contributors are returned, ordered by contribution.

## Evaluation

The engine was evaluated against independently generated synthetic reference labels on 77,050 records. Metrics are taken directly from `ml/models/model3_metrics.json`:

| Metric | Value |
|---|---:|
| Accuracy | 0.824 |
| Macro precision | 0.7982 |
| Macro recall | 0.7621 |
| Macro F1 | 0.7795 |
| HIGH precision | 0.8124 |
| HIGH recall | 0.6988 |
| HIGH F1 | 0.7512 |

The class order for its confusion matrix is LOW, MEDIUM, HIGH (see `ml/models/model3_metrics.json`). These scores evaluate agreement with independent synthetic reference labels; they are not calibrated probabilities.

## Model Artifact

```text
ml/models/model3_risk_engine_config.json
```

The JSON policy contains the version, feature weights, scoring rules, missing-value behaviour, and risk thresholds. The backend reads it for inference, so policy changes remain inspectable and versioned.

---

# Overall Three-Component Architecture

```text
                    STUDENT DATA
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
        MODEL 1      MODEL 2      MODEL 3
       End-Term     Pass/Fail    Risk Engine
        Marks       Probability  Score + Level
             |           |           |
             +-----------+-----------+
                         v
                  ACADEMIC INSIGHTS
```

| Component | Type | Primary output | Artifact |
|---|---|---|---|
| Model 1 | Regression | Predicted end-term marks | `model1_endterm_histgradientboosting.pkl` |
| Model 2 | Binary classification | PASS/FAIL plus probabilities | `model2_pass_fail_histgradientboosting.pkl` |
| Model 3 | Rule-based risk engine v1.1 | Risk score, level, completeness, and factors | `model3_risk_engine_config.json` |

---

# Important Limitations

The CBCS data is synthetic and the evaluation results should not be interpreted as guaranteed institutional performance. Models should be monitored and retrained when representative institutional outcomes become available.

Model 3 is a policy engine, not a causal model or calibrated probability. Its weights and thresholds should be reviewed with academic experts and compared with observed intervention outcomes.

---

# Current Project Status

```text
Model 1
[COMPLETED]
model1_endterm_histgradientboosting.pkl

Model 2
[COMPLETED]
model2_pass_fail_histgradientboosting.pkl

Model 3
[COMPLETED - RULE ENGINE v1.1]
model3_risk_engine_config.json

FastAPI Integration
[IMPLEMENTED]
```