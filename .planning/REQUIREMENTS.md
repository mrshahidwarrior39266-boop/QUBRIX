# Requirements: Rubric-Based Short-Answer Grader

**Defined:** 2026-11-17  
**Core Value:** Provide instant, explainable, evidence-backed short-answer grading with sub-second dynamic re-grading and psychometric Quadratic Weighted Kappa agreement against human teachers.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion & Data Pipeline

- [ ] **INGEST-01**: User can load questions, model answers, configurable rubrics, and batch student answers from CSV files across multiple subjects.
- [ ] **INGEST-02**: System validates CSV schema and normalizes subjects (e.g., Biology, Computer Science, History).

### Semantic Similarity & Baseline Scoring

- [ ] **SIM-01**: System computes cosine similarity between student answer and model answer using `sentence-transformers/all-MiniLM-L6-v2`.
- [ ] **SIM-02**: System produces an overall semantic match index (0–100%) for each student answer.

### Rubric Reasoning & Evidence Extraction

- [ ] **RUBRIC-01**: System evaluates each rubric criterion as `FULL`, `PARTIAL`, or `NONE` using structured LLM JSON outputs.
- [ ] **RUBRIC-02**: System awards marks according to the configured criterion weight and fulfillment status.
- [ ] **EVIDENCE-01**: System extracts exact verbatim phrases from the student answer justifying each awarded mark.
- [ ] **EVIDENCE-02**: System verifies that extracted quotes exist as character-for-character substrings within the raw student answer.

### Student Feedback

- [ ] **FEEDBACK-01**: System synthesizes constructive feedback focused on missed rubric points.
- [ ] **FEEDBACK-02**: System strictly prevents model answer leakage by offering socratic conceptual hints rather than canonical solutions.

### Reliability & Agreement Analysis

- [ ] **METRIC-01**: System computes Quadratic Weighted Kappa (QWK) between system scores and human ground-truth marks using `scikit-learn`.
- [ ] **METRIC-02**: System flags borderline or highly divergent answers ($|Score_{AI} - Score_{Human}| \ge \Delta$) for teacher manual review.

### Dynamic Regrading & Diffing

- [ ] **REGRADE-01**: System stores rubrics purely as configuration, allowing teachers to dynamically reweight points or add criteria without retraining or code changes.
- [ ] **REGRADE-02**: System recalculates batch scores in $<10\text{ms}$ upon weight adjustment using decoupled deterministic arithmetic.
- [ ] **DIFF-01**: System renders a before-and-after score diff table highlighting point delta and justification for every student.

### User Interface & Demo Safety

- [ ] **UI-01**: Interactive Streamlit dashboard with multi-subject selector tabs and responsive data views.
- [ ] **UI-02**: Visual inline color-coded `<mark>` highlighting of evidence spans directly on student answers.
- [ ] **CACHE-01**: Persistent local disk cache for evaluations ensuring 100% demo uptime and API rate-limit resilience.
- [ ] **EXPORT-01**: User can export batch grading reports with itemized criteria marks and feedback as CSV.

## v2 Requirements

Deferred to future releases.

- **V2-AUDIO-01**: Audio text-to-speech synthesis of student feedback for accessibility.
- **V2-LMS-01**: Direct Canvas / Google Classroom LTI integration.
- **V2-RADAR-01**: Longitudinal student learning progression radar charts across semesters.

## Out of Scope

| Feature | Reason |
|---|---|
| User Authentication & Login | 12-hour hackathon constraint; distracts from grading engine and wastes demo time |
| Fine-Tuning Custom BERT/DeBERTa | Overfits small samples, requires hours of training, breaks on unseen subjects |
| Microservices / Kubernetes | Over-engineering; single-process Python application runs in 1 command |
| Heavy SQL Databases | In-memory Pandas + JSON cache handles batch grading with zero server overhead |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|---|---|---|
| INGEST-01, INGEST-02 | Phase 1 | Complete ✓ |
| SIM-01, SIM-02 | Phase 1 | Complete ✓ |
| RUBRIC-01, RUBRIC-02, EVIDENCE-01, EVIDENCE-02 | Phase 2 | Complete ✓ |
| FEEDBACK-01, FEEDBACK-02 | Phase 2 | Complete ✓ |
| METRIC-01, METRIC-02 | Phase 3 | Complete ✓ |
| REGRADE-01, REGRADE-02, DIFF-01 | Phase 3 | Complete ✓ |
| UI-01, UI-02, CACHE-01, EXPORT-01 | Phase 4 | Complete ✓ |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-17*  
*Last updated: 2026-11-17 after initialization from PLAN.md*
