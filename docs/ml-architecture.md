# ML Architecture: SupplySense Nexus

## Overview

The ML system follows a time-based validation approach for forecasting tasks and constraint-based optimization for procurement tasks. All models are versioned, reproducible, and evaluated with standardized metrics.

## Data Preparation

1. **Loading**: Pull demand observations from PostgreSQL.
2. **Cleaning**: Handle missing values, remove outliers using IQR or domain rules.
3. **Temporal Splitting**: Split data chronologically - training, validation, test sets.
4. **Normalization**: Scale numerical features appropriately per model type.
5. **Labeling**: All training data carries a `data_source_label` in metadata.

**Key Principle**: No future data leaks into training. Time-based splits only.

## Feature Engineering

### Time-Based Features
- Day of week, month, quarter, week of year
- Holiday indicators (from public holiday calendars)
- Lag features (1-day, 7-day, 14-day, 28-day lags)
- Rolling statistics (7-day, 14-day, 28-day mean and std)
- Exponential moving averages

### External Features
- Seasonality indicators (Fourier terms for yearly/weekly patterns)
- Pricing changes (if available)
- Promotional indicators (if available)

### Derived Features
- Year-over-year growth rate
- Month-over-month change
- Percentage change from moving average

## Baseline Models

### 1. Naive Forecast
- **Method**: Predict last observed value.
- **Formula**: ŷ(t+h) = y(t)
- **Use Case**: Benchmark for non-seasonal data.
- **Evaluation**: MAE, RMSE, MAPE

### 2. Seasonal Naive Forecast
- **Method**: Predict value from the same season in the previous cycle.
- **Formula**: ŷ(t+h) = y(t - h + season_length * k)
- **Use Case**: Benchmark for seasonal data.
- **Evaluation**: MAE, RMSE, MAPE

### 3. Moving Average
- **Method**: Predict the average of the last N observations.
- **Formula**: ŷ(t+h) = mean(y(t-N+1), ..., y(t))
- **Use Case**: Smooth, stable demand patterns.
- **Evaluation**: MAE, RMSE, MAPE

### 4. Exponential Smoothing (SES/Holt-Winters)
- **Method**: Weighted average with exponential decay.
- **Variants**: Simple, Holt's linear trend, Holt-Winters seasonal.
- **Use Case**: Data with trend and/or seasonality.
- **Evaluation**: MAE, RMSE, MAPE, sMAPE

### 5. Gradient Boosting (Justified ML Baseline)
- **Method**: Gradient-boosted decision trees on engineered features.
- **Implementation**: Scikit-learn HistGradientBoostingRegressor or equivalent.
- **Use Case**: Captures nonlinear patterns and feature interactions.
- **Evaluation**: MAE, RMSE, MAPE, WMAPE, R²

**No claims are made about model performance until models are trained and evaluated.**

## Time-Based Validation

### Walk-Forward Validation
1. Train on data from T_start to T_end.
2. Validate on T_end+1 to T_end+H.
3. Expand training window by H and repeat.
4. Final evaluation on held-out test set.

### Split Strategy
- **Training**: 60% of available history
- **Validation**: 20% of available history
- **Test**: 20% of available history (most recent)
- **No shuffling**: Temporal order is preserved.

## Evaluation Metrics

### Primary Metrics
- **MAE** (Mean Absolute Error): Average absolute deviation.
- **RMSE** (Root Mean Squared Error): Penalizes larger errors.
- **MAPE** (Mean Absolute Percentage Error): Percentage error.
- **sMAPE** (Symmetric MAPE): Symmetric percentage error.

### Secondary Metrics
- **WMAPE** (Weighted MAPE): Volume-weighted percentage error.
- **R²** (Coefficient of Determination): Variance explained.
- **MASE** (Mean Absolute Scaled Error): Scale-independent metric.

### Interval Metrics
- **Coverage**: Fraction of actuals within prediction intervals.
- **Interval Width**: Average width of prediction intervals.
- **PINBALL Loss**: Proper scoring rule for quantile forecasts.

## Prediction Intervals

### Approach
1. **Residual-Based**: Fit distribution to model residuals; compute quantiles.
2. **Bootstrap**: Resample residuals and refit; compute empirical intervals.
3. **Conformal Prediction**: Use conformal prediction for distribution-free intervals.

### Requirements
- All forecasts include prediction intervals at 80% and 95% confidence.
- Intervals are labeled as simulated/estimated outputs.
- Interval coverage is monitored for drift.

## Model Selection

### Process
1. Train all baseline models on the training window.
2. Evaluate on the validation window using primary metrics.
3. Select the model with the best validation performance.
4. Final evaluation on the held-out test set.
5. Register the selected model version in the model registry.

### Criteria
- Primary metric: WMAPE or MAPE (business-relevant).
- Secondary consideration: Prediction interval quality.
- Tie-breaker: Simplicity and interpretability.

## Model Versioning

### Model Registry Schema
- Model name, type, version string.
- Training window dates.
- Evaluation metrics (MAE, RMSE, MAPE, WMAPE).
- Feature engineering configuration.
- Serialized model file path.
- Active/inactive status.
- Registration timestamp and user.

### Versioning Rules
- Each training run produces a new version.
- Only one model version is active per product per horizon.
- Model rollback is supported by activating a previous version.
- Full reproducibility via fixed random seeds and configuration snapshots.

## Drift Monitoring

### Data Drift
- Compare feature distributions between training and production.
- Use Kolmogorov-Smirnov test or Population Stability Index (PSI).
- Alert when PSI exceeds threshold (e.g., 0.2).

### Prediction Drift
- Monitor forecast accuracy on recent observations.
- Track WMAPE on a rolling window.
- Alert when accuracy degrades beyond threshold.

### Concept Drift
- Monitor changes in demand patterns (seasonality shifts, trend changes).
- Compare recent model performance against validation metrics.
- Trigger retraining when drift is detected.

## Explainability

### Feature Importance
- Tree-based models: Built-in feature importance scores.
- SHAP values for model-agnostic explanation.
- Time-shap for temporal feature contributions.

### Forecast Breakdown
- Show contribution of each feature to the forecast.
- Highlight key drivers (lag effects, seasonality, trends).
- Present in human-readable format for business stakeholders.

## Reproducibility

- **Random Seeds**: All stochastic processes use fixed seeds (default: 42).
- **Configuration Snapshots**: Every training run stores its configuration.
- **Data Versioning**: Training data is versioned with dataset identifiers.
- **Environment**: Python package versions are pinned.
- **Model Artifacts**: Serialized models stored with version metadata.

## Failure Handling

1. **Training Failure**: Log error, fallback to previous model version.
2. **Inference Failure**: Return baseline naive forecast with warning.
3. **Data Quality Failure**: Reject training data; alert data team.
4. **Drift Detected**: Trigger retraining pipeline; notify analysts.
5. **Model Degradation**: Revert to previous version; schedule investigation.

## Future ML Extensions

- **XGBoost/LightGBM**: For improved gradient boosting performance.
- **Prophet**: For automated seasonal forecasting.
- **Deep Learning**: LSTM/Transformer models for complex patterns.
- **Great Expectations**: For formal data-quality validation.
- **MLflow**: For comprehensive model tracking and registry.
