# Rubric-Based Short-Answer Grader (RubricGrader AI)

## What This Is

An explainable, auditable AI grading assistant for academic teachers that scores short student answers against configurable rubrics across any subject, highlights exact verbatim evidence from the student's text, provides constructive feedback without leaking model answers, and recalculates grades in milliseconds when rubrics evolve. Built for the QUBRIX 12-Hour Internal Hackathon (AIML Problem 2).

## Core Value

Provide instant, explainable, evidence-backed short-answer grading with sub-second dynamic re-grading and psychometric Quadratic Weighted Kappa agreement against human teachers.

## Business Context

- **Customer**: Academic educators, exam boards, universities, and online learning platforms burdened by subjective grading inconsistency and slow turnaround times.
- **Success metric**: Quadratic Weighted Kappa (QWK) agreement with human examiners $\ge 0.75$ and sub-10ms dynamic re-grading response time.
- **Strategy notes**: Synthesized from [PLAN.md](../PLAN.md) based on QUBRIX hackathon specifications.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **INGEST-01**: Ingest and parse batch CSV files containing Questions, Model Answers, Multi-Criteria Rubrics, Student Answers, and Human Ground-Truth Scores across multiple subjects.
- [ ] **SIM-01**: Compute semantic similarity overall score (0–100%) against the model answer using local dense vector embeddings (`all-MiniLM-L6-v2`).
- [ ] **RUBRIC-01**: Evaluate student answers per rubric criterion (`FULL`, `PARTIAL`, `NONE`) using structured JSON reasoning.
- [ ] **EVIDENCE-01**: Extract exact verbatim text quotes from the student's answer and validate substring existence in raw text.
- [ ] **FEEDBACK-01**: Synthesize socratic, constructive feedback addressing missed rubric points without leaking the model answer.
- [ ] **METRIC-01**: Compute Quadratic Weighted Kappa (QWK) agreement against human grader scores via `sklearn.metrics.cohen_kappa_score`.
- [ ] **AUDIT-01**: Flag borderline or highly divergent answers ($|Score_{AI} - Score_{Human}| \ge \text{threshold}$) for teacher human-in-the-loop review.
- [ ] **REGRADE-01**: Configuration-driven dynamic re-grading engine that re-weights criteria and recalculates scores in $<10\text{ms}$ with zero model retraining.
- [ ] **DIFF-01**: Render a Before-and-After score diff table detailing point changes and rationale per student.
- [ ] **UI-01**: Streamlit dashboard with multi-subject tabs, inline color-coded `<mark>` highlighted text spans, and dynamic weight sliders.
- [ ] **CACHE-01**: Persistent local disk cache for API evaluations ensuring rate-limit immunity and 100% offline demo safety.
- [ ] **EXPORT-01**: Export batch graded report with itemized criteria marks and feedback to downloadable CSV.

### Out of Scope

- **User Authentication / Role Management (Auth0/Firebase)** — Excluded to protect the 12-hour hackathon clock; adds zero value to live judge evaluation.
- **Custom Model Fine-Tuning (BERT/DeBERTa)** — Excluded because fine-tuning overfits small samples, takes hours, and fails on unseen subjects.
- **Microservices / Kubernetes / Distributed Workers** — Excluded in favor of a single-process, highly responsive Python architecture.
- **External Heavy Database (PostgreSQL/MongoDB)** — Excluded in favor of in-memory Pandas and local JSON caching.

## Context

- Hackathon environment: 12-hour clock, Windows developer laptop, standard Python 3.13 environment.
- Evaluation emphasizes: Agreement with human grading on unseen answers/subjects, flexibility of configuration-driven regrading, evidence quote quality, and usefulness of feedback.
- Architecture decouples qualitative evidence extraction from mathematical scoring arithmetic to enable zero-cost, instant re-grading.

## Constraints

- **Timeline**: 12 hours from start to feature freeze and demo rehearsal.
- **Compute**: Local CPU-friendly execution (80MB MiniLM embedding model + cloud LLM API with offline mock fallback).
- **Offline Resilience**: Must maintain full demo functionality even if venue Wi-Fi drops or API rate limits trigger.
- **Auditability**: Every mark awarded must be supported by an exact verbatim quote from the student's submission.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Streamlit over React+FastAPI | Pure Python reactive UI saves 4+ hours of full-stack wiring | ✓ Good |
| Local `all-MiniLM-L6-v2` for Semantic Similarity | Fast (10ms on CPU), free, 100% offline-capable, 384-dim dense vector space | ✓ Good |
| Gemini Flash with JSON Schema for Rubric Extraction | Guaranteed structured schema, low latency (~800ms), generous free tier | ✓ Good |
| Decoupled Evaluation & Arithmetic Engine | Separates semantic status extraction from weight math, enabling instant $O(1)$ re-grading | ✓ Good |
| Scikit-Learn `cohen_kappa_score` for QWK | Official standard for inter-rater reliability in automated scoring | ✓ Good |
| Inline HTML `<mark>` Tags for Highlighting | Zero third-party React package dependencies, reliable rendering in Streamlit | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-17 after initialization from PLAN.md*
