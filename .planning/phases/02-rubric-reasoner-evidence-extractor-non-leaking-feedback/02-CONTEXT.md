# Phase 2 Context: Rubric Reasoner, Evidence Extractor & Non-Leaking Feedback

## Phase Goal
Implement explainable per-criterion rubric scoring, verbatim quote extraction with character-accurate substring validation, and socratic student feedback that strictly prevents model answer leakage.

## Requirements Covered
- **RUBRIC-01**: Evaluate each criterion as `FULL`, `PARTIAL`, or `NONE` via structured JSON.
- **RUBRIC-02**: Award marks based on criterion weight and fulfillment multiplier (1.0, 0.5, 0.0).
- **EVIDENCE-01**: Extract exact verbatim quotes from the student answer justifying marks.
- **EVIDENCE-02**: Verify that cited quotes exist as character-for-character substrings in student text.
- **FEEDBACK-01**: Synthesize constructive feedback focused on missed rubric points.
- **FEEDBACK-02**: Strictly prevent model answer leakage using automated 4-gram overlap filters.

## Key Technical Decisions
- **Decoupled Architecture**: Qualitative fulfillment states (`FULL`, `PARTIAL`, `NONE`) are stored independently of numeric weights so teachers can adjust weights in Phase 3 without calling the LLM again.
- **Verbatim Guard**: The engine programmatically verifies `quote in student_answer`. If an LLM hallucination occurs, the quote is marked unverified or replaced with the closest extracted span.
- **Anti-Leakage Guard**: An n-gram tokenizer checks student feedback against the instructor's model answer to ensure no $\ge 4$-word sequences from the answer key are inadvertently revealed.

## Plans in this Phase
1. `02-01-PLAN.md` (Wave 1): Rubric evaluator, structured JSON schema, verbatim quote validator in `core/rubric_evaluator.py`.
2. `02-02-PLAN.md` (Wave 2): Non-leaking socratic feedback engine in `core/feedback_engine.py`.
