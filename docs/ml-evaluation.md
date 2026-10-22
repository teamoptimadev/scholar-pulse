# ML Evaluation

Evaluation metrics for the three academic intelligence components, derived from the synthetic CBCS datasets and the versioned risk-engine evaluation.

## Train/Test Split

| Model | Split | Stratify | random_state |
|-------|-------|----------|--------------|
| Model 1 (regression) | GroupShuffleSplit by student | No | 42 |
| Model 2 (classification) | StratifiedGroupKFold by student | Yes | 42 |
| Model 3 (rule engine) | Independent synthetic reference labels | N/A | N/A |

## Model 1 — Performance Prediction (Regression)

| Metric | Value |
|--------|-------|
| MAE | 5.65486118852561 |
| RMSE | 7.089512420739615 |
| R² | 0.757390134321228 |

**Algorithm:** HistGradientBoostingRegressor in sklearn Pipeline

## Model 2 — Pass/Fail Prediction (Classification)

| Metric | Value |
|--------|-------|
| Accuracy | 0.9595027664008048 |
| Precision (FAIL) | 0.1606015037593985 |
| Recall (FAIL) | 0.9518716577540107 |
| F1 (FAIL) | 0.2748327328872877 |
| ROC-AUC | 0.9912483616745048 |

**Algorithm:** HistGradientBoostingClassifier

### Why FAIL Recall Matters

In academic intervention systems, missing a failing student (false negative) is worse than a false alarm. The selected model prioritizes FAIL recall and ROC-AUC.

### Class Distribution

The test set contains 69,585 rows and 561 FAIL rows (see `ml/models/model2_metrics.json`).

## Model 3 — At-Risk Detection (Rule Engine)

Model 3 is **not** an ML classifier. It is the transparent weighted risk engine version 1.1.

### Evaluation Metrics

| Level | Count | % |
|-------|-------|---|
| Accuracy | 0.824 |
| Macro precision | 0.7982 |
| Macro recall | 0.7621 |
| Macro F1 | 0.7795 |
| HIGH precision | 0.8124 |
| HIGH recall | 0.6988 |
| HIGH F1 | 0.7512 |

### Validation

- Config JSON weights and thresholds verified on reload.
- Missing history indicators contribute 0; missing behaviour and prior-attainment indicators contribute half of their weight.
- An all-missing student scores 25.0 and is classified MEDIUM.

## Caveats

- The synthetic datasets are not production guarantees.
- Model 3 weights are heuristic, not ML-optimized.

## Running Tests

```bash
cd ml && uv sync && uv run pytest
```

## Future: Explainability

SHAP explainability for classification models is a future enhancement when FastAPI integration is implemented. Model 3 already provides human-readable `risk_indicators`.

## Related Documentation

- [ML Pipeline](ml-pipeline.md)
- [Dataset](dataset.md)
- [Dataset Documentation](../ml/models/dataset_documentation.md)
- [Development Phases](development-phases.md)
