# Phase 3 Context: Reliability Analysis & Dynamic Regrading Engine

## Phase Goal
Implement Quadratic Weighted Kappa (QWK) psychometric agreement measurement, automated borderline discrepancy flagging, and sub-10ms decoupled dynamic rubric re-grading with before-and-after score diffing.

## Requirements Covered
- **METRIC-01**: Compute Quadratic Weighted Kappa (QWK) agreement vs human examiner scores using `sklearn.metrics.cohen_kappa_score(..., weights="quadratic")`.
- **METRIC-02**: Flag borderline or highly divergent answers ($|Score_{AI} - Score_{Human}| \ge \Delta$) for teacher manual review.
- **REGRADE-01**: Treat rubrics purely as configuration so teachers can reweight marks or add criteria without retraining or code changes.
- **REGRADE-02**: Recalculate batch scores in $<10\text{ms}$ upon weight adjustment using decoupled deterministic arithmetic.
- **DIFF-01**: Render a Before-and-After score diff table detailing point changes and rationale per student.

## Key Technical Decisions
- **Discretized QWK Rating Scales**: Continuous float scores are mapped to discrete ordinal bins (e.g. rounded to nearest half-unit) so the quadratic penalty matrix accurately penalizes large discrepancies.
- **Decoupled Math Execution**: Rather than calling an LLM, the regrading engine applies user slider weights directly to the stored fulfillment multiplier (`FULL=1.0`, `PARTIAL=0.5`, `NONE=0.0`), completing batch regrading in under 2 milliseconds.
- **Explainable Diffs**: The diff engine produces human-readable explanations explaining why each student gained or lost marks.

## Plans in this Phase
1. `03-01-PLAN.md` (Wave 1): QWK metrics calculator and borderline triage queue in `core/metrics.py`.
2. `03-02-PLAN.md` (Wave 2): Sub-10ms dynamic regrading and before/after diffing in `core/regrading_engine.py`.
