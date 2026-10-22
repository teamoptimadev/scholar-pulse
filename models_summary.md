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

## Feature Importance, Ablation, and Threshold-Cost Analysis

All results below use the held-out student-level test splits: Model 1 has 53,971 rows from 2,000 students; Model 2 has 69,585 rows from 1,995 students (561 FAIL rows). Permutation importance uses five repeats and the full held-out split. Model 1 importance is the increase in MAE; Model 2 importance is the decrease in average precision for FAIL.

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

Full feature rankings, including standard deviations, are in `ml/models/model1_feature_importance.csv` and `ml/models/model2_feature_importance.csv`.

### Feature-group ablation

Each row is a fresh clone of the corresponding full pipeline fit on the training split. Metric deltas are relative to the full-model row; lower MAE/RMSE and higher R² are better for Model 1.

| Model 1 configuration | MAE (Δ) | RMSE (Δ) | R² (Δ) |
|---|---:|---:|---:|
| Full model | 5.654861 (0.000000) | 7.089512 (0.000000) | 0.757390 (0.000000) |
| Drop `MID_mark` only | 5.942767 (+0.287906) | 7.458517 (+0.369004) | 0.731478 (-0.025913) |
| Drop all Assessments | 8.345810 (+2.690949) | 10.456414 (+3.366901) | 0.472234 (-0.285156) |
| Drop Engagement / Behavioral | 5.661289 (+0.006428) | 7.096271 (+0.006758) | 0.756927 (-0.000463) |
| Drop Prior Academic History | 5.827282 (+0.172421) | 7.301853 (+0.212341) | 0.742639 (-0.014751) |

For Model 2, recall and precision use the pipeline's default predicted class; PR-AUC uses the probability of FAIL. Higher values are better for all four metrics.

| Model 2 configuration | FAIL Recall (Δ) | FAIL Precision (Δ) | PR-AUC (Δ) | ROC-AUC (Δ) |
|---|---:|---:|---:|---:|
| Full model | 0.951872 (0.000000) | 0.160602 (0.000000) | 0.584915 (0.000000) | 0.991248 (0.000000) |
| Drop `MID_mark` only | 0.934046 (-0.017825) | 0.145193 (-0.015409) | 0.507328 (-0.077587) | 0.988774 (-0.002475) |
| Drop all Assessments | 0.957219 (+0.005348) | 0.109257 (-0.051344) | 0.291416 (-0.293499) | 0.982110 (-0.009138) |
| Drop Engagement / Behavioral | 0.960784 (+0.008913) | 0.161136 (+0.000535) | 0.605520 (+0.020605) | 0.991798 (+0.000550) |
| Drop Prior Academic History | 0.698752 (-0.253119) | 0.030022 (-0.130579) | 0.354163 (-0.230752) | 0.876645 (-0.114603) |

### Model 2 threshold-cost sweep

`p(FAIL) >= threshold` flags an enrollment for review. The test set contains 561 true FAILs. “False alerts / TP” is FP divided by TP; flagged percentage is measured over all 69,585 test enrollments.

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

The high-recall policy selects the listed sweep threshold with at least 90% FAIL recall and the fewest false alerts. No listed sweep threshold satisfies the 2.0% capacity cap, so the capacity policy uses the lowest observed probability score that stays within the 1,391-enrollment limit.

| Model | Policy | Threshold | TP | FP | FN | FAIL Recall | FAIL Precision | Flagged |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Full | High-recall screening | 0.70 | 517 | 2,030 | 44 | 0.9216 | 0.2030 | 3.660% |
| CA-only | High-recall screening | 0.60 | 513 | 2,663 | 48 | 0.9144 | 0.1615 | 4.564% |
| Full | Capacity-constrained (≤2.0%) | 0.883089 | 442 | 949 | 119 | 0.7879 | 0.3178 | 1.999% |
| CA-only | Capacity-constrained (≤2.0%) | 0.886314 | 409 | 982 | 152 | 0.7291 | 0.2940 | 1.999% |

Machine-readable complete results and methodology are in `ml/models/ablation_and_threshold_analysis.json`.