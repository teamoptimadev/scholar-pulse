# Dataset Strategy

## Overview

The ML models are trained on a synthetic CBCS university dataset in `university_data/*.csv`. Its schema and generation logic are documented in [dataset documentation](../ml/models/dataset_documentation.md).

| Property | Value |
|----------|-------|
| Source | Synthetic CBCS university data |
| Files | `university_data/*.csv` |
| Schema | [dataset documentation](../ml/models/dataset_documentation.md) |


## Columns

### Targets and Derived Labels

| Column | Role |
|--------|------|
| `TARGET_END_MARKS` | End-term marks from 0 to 100 — target for Model 1 |
| `TARGET_PASS_FAIL` | PASS/FAIL target for Model 2 |


### Model Input Features

Model 1 uses `CA_mark`, `MID_mark`, `attendance_percentage`, `study_hours_per_week`, `assignment_completion_pct`, `previous_sgpa`, `previous_cgpa`, `backlog_count`, `course_credits`, `course_type`, `branch`, and `semester`.

Model 2 uses the same features except `course_type`.

### Model 3 Inputs

Model 3 uses `attendance_percentage`, `previous_cgpa`, `backlog_count`, `current_failed_courses`, `low_performance_course_count`, `study_hours_per_week`, `assignment_completion_percentage`, and `performance_trend`.

## Processed Data


The model training datasets are `model1_regression_dataset.csv` and `model2_pass_fail_dataset.csv`; they contain different row sets.

## Backend Seed Data (Future)

PostgreSQL development data is loaded via `backend/scripts/seed.py`.

## Related Documentation

- [ML Pipeline](ml-pipeline.md)
- [ML Evaluation](ml-evaluation.md)
- [ML Data Documentation](../ml/models/dataset_documentation.md)
