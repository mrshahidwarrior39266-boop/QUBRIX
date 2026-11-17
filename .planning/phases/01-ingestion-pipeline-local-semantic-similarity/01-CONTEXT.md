# Phase 1 Context: Ingestion Pipeline & Local Semantic Similarity

## Phase Goal
Build the data foundation for the Rubric-Based Short-Answer Grader: multi-subject CSV dataset fixtures (Biology, Computer Science, History) and the local semantic vector similarity engine (`all-MiniLM-L6-v2`) with automatic TF-IDF fallback.

## Requirements Covered
- **INGEST-01**: Ingest batch CSV files containing Questions, Model Answers, Multi-Criteria Rubrics, Student Answers, and Human Ground-Truth Scores across multiple subjects.
- **INGEST-02**: Validate CSV schema and normalize subject records.
- **SIM-01**: Compute cosine similarity between student answer and model answer using dense embeddings.
- **SIM-02**: Produce an overall semantic match index (0–100%) for each student answer.

## Key Technical Decisions
- **Dataset Structure**: 3 distinct subjects to validate cross-subject generalization (Biology, CS, History) with varied quality responses (full, partial, poor).
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` running on local CPU (80MB, ~10ms per sentence).
- **Zero-Network Fallback**: Scikit-Learn TF-IDF vectorizer fallback if Hugging Face weights fail to download, ensuring zero-downtime execution.

## Plans in this Phase
1. `01-01-PLAN.md` (Wave 1): Benchmark CSV datasets and schema-validating `core/data_loader.py`.
2. `01-02-PLAN.md` (Wave 2): Local dense embedding vector similarity in `core/similarity_engine.py`.
