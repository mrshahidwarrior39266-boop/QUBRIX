# Roadmap: Rubric-Based Short-Answer Grader

## Overview

A focused 4-phase execution roadmap designed for the QUBRIX 12-hour hackathon. We build from the ground up: establishing clean multi-subject data ingestion and local semantic similarity in Phase 1, engineering LLM-powered verbatim evidence extraction and feedback in Phase 2, implementing Quadratic Weighted Kappa and the zero-latency dynamic regrader in Phase 3, and delivering an ultra-polished Streamlit dashboard with span highlighting and offline caching in Phase 4.

## Phases

- [x] **Phase 1: Ingestion Pipeline & Local Semantic Similarity** - CSV parsing across multiple subjects and dense vector embedding cosine similarity against model answers.
- [x] **Phase 2: Rubric Reasoner, Evidence Extractor & Non-Leaking Feedback** - Structured JSON evaluation of rubric criteria, verbatim quote extraction with substring guards, and socratic feedback synthesis.
- [x] **Phase 3: Reliability Analysis & Dynamic Regrading Engine** - Quadratic Weighted Kappa calculation, borderline teacher triage, and sub-10ms decoupled rubric re-weighting with before/after diffing.
- [x] **Phase 4: Streamlit Interactive Dashboard & Demo Polish** - Full UI with multi-subject tabs, inline `<mark>` evidence highlighting, dynamic sliders, CSV report export, and offline cache safety.

---

## Phase Details

### Phase 1: Ingestion Pipeline & Local Semantic Similarity
**Goal**: Ingest multi-subject CSV files (Biology, CS, History) and compute local dense embedding cosine similarity against model answers without external API calls.  
**Depends on**: Nothing (first phase)  
**Requirements**: INGEST-01, INGEST-02, SIM-01, SIM-02  
**Success Criteria** (what must be TRUE):
  1. System loads and parses sample CSVs with question, model answer, rubric points, student answers, and human scores.
  2. `all-MiniLM-L6-v2` generates 384-dimensional dense embeddings for model and student answers on local CPU.
  3. Cosine similarity between student answers and model answers is computed and scaled to a 0–100% semantic score.
**Plans**: 2 plans

Plans:
- [x] 01-01: Build multi-subject CSV dataset fixtures and schema validator in `core/data_loader.py`.
- [x] 01-02: Implement local embedding and cosine similarity engine in `core/similarity_engine.py`.

---

### Phase 2: Rubric Reasoner, Evidence Extractor & Non-Leaking Feedback
**Goal**: Evaluate each student answer against configured rubric points, extract verbatim text quotes with character-exact validation, and generate constructive feedback without leaking the model answer.  
**Depends on**: Phase 1  
**Requirements**: RUBRIC-01, RUBRIC-02, EVIDENCE-01, EVIDENCE-02, FEEDBACK-01, FEEDBACK-02  
**Success Criteria** (what must be TRUE):
  1. System extracts structured JSON specifying fulfillment (`FULL`, `PARTIAL`, `NONE`) for every rubric criterion.
  2. Every piece of cited evidence is verified as a literal substring of the student's submission.
  3. Student feedback addresses conceptual deficiencies socratically without quoting the model answer.
**Plans**: 2 plans

Plans:
- [x] 02-01: Implement structured LLM evaluation and verbatim quote validator in `core/rubric_evaluator.py`.
- [x] 02-02: Implement socratic feedback synthesizer with negative-leakage guardrails in `core/feedback_engine.py`.

---

### Phase 3: Reliability Analysis & Dynamic Regrading Engine
**Goal**: Compute Quadratic Weighted Kappa (QWK) against human teacher scores, flag borderline cases, and build the instant decoupled rubric re-weighting and diffing engine.  
**Depends on**: Phase 2  
**Requirements**: METRIC-01, METRIC-02, REGRADE-01, REGRADE-02, DIFF-01  
**Success Criteria** (what must be TRUE):
  1. System calculates Quadratic Weighted Kappa using `sklearn.metrics.cohen_kappa_score` with `weights="quadratic"`.
  2. Answer submissions with $|Score_{AI} - Score_{Human}| \ge \text{threshold}$ are automatically flagged as borderline.
  3. Modifying rubric weights recalculates all batch scores and outputs a before-and-after diff in $<10\text{ms}$.
**Plans**: 2 plans

Plans:
- [x] 03-01: Build QWK metrics calculator and borderline triage auditor in `core/metrics.py`.
- [x] 03-02: Build decoupled deterministic re-grading and before/after score diff engine in `core/regrading_engine.py`.

---

### Phase 4: Streamlit Interactive Dashboard & Demo Polish
**Goal**: Assemble an executive-grade Streamlit web interface with subject tabs, color-coded HTML text highlights, dynamic sliders, and offline disk caching.  
**Depends on**: Phase 3  
**Requirements**: UI-01, UI-02, CACHE-01, EXPORT-01  
**Success Criteria** (what must be TRUE):
  1. User can switch between Biology, CS, and History or upload new CSVs in the UI.
  2. Student answers display color-coded inline `<mark>` tags highlighting the exact evidence for each mark.
  3. Sliders dynamically update rubric weights in real time and refresh the Before-and-After score diff table.
  4. Local cache persists evaluations so demo runs instantly even without internet access.
  5. Graded batch results with itemized feedback export to CSV in one click.
**Plans**: 2 plans

Plans:
- [x] 04-01: Build Streamlit application (`app.py`) with subject tabs, highlight cards, sliders, and diff table.
- [x] 04-02: Add offline disk cache, CSV report export, and package demo-safety runbook.

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 1. Ingestion Pipeline & Semantic Vector Engine | 2/2 | Complete | 2026-11-17 |
| 2. Rubric Reasoner & Evidence Extractor | 2/2 | Complete | 2026-11-17 |
| 3. Reliability Analysis & Dynamic Regrading Engine | 2/2 | Complete | 2026-11-17 |
| 4. Streamlit Interactive Dashboard & Demo Polish | 2/2 | Complete | 2026-11-17 |
