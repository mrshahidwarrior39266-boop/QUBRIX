# Plan Summary: 03-01 Psychometric Reliability Analysis & Borderline Triage

## Plan Reference
- **Phase**: 03 (Reliability Analysis & Dynamic Regrading Engine)
- **Plan**: 01
- **Requirements Satisfied**: METRIC-01, METRIC-02

## What Was Built
1. **Psychometric Reliability Engine (`core/metrics.py`)**:
   - `calculate_qwk`: Computes Quadratic Weighted Kappa (QWK) using `sklearn.metrics.cohen_kappa_score(..., weights="quadratic")`.
   - Ordinal binning maps continuous floats to discrete grade scales to build valid quadratic penalty matrices.
   - Computes supporting statistics: Mean Absolute Error (MAE), exact agreement %, adjacent agreement %, and qualitative interpretation tiers ('Near Perfect Agreement', 'Substantial Agreement', etc.).
2. **Borderline Discrepancy Flagging**:
   - `flag_borderline_answers`: Computes $|Score_{AI} - Score_{Human}|$, flags answers exceeding the configurable threshold (default $\Delta \ge 1.5$), and produces an explicit teacher review queue with diagnosis tags.
3. **Automated Unit Tests**:
   - `tests/test_metrics.py`: 4 unit tests verifying perfect agreement, substantial agreement, severe penalty on inverted scores, and borderline flagging.

## Verification
- Automated unit test suite executed:
  `python -m unittest tests/test_metrics.py`
  Result: **4/4 tests passed in 0.031s**.
