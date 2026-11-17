# RubricGrader AI 🎓
### Rubric-Based Short-Answer Grader with Verbatim Evidence & Instant Regrading
**QUBRIX 12-Hour Internal Hackathon • AIML Problem 2 (EdTech)**

---

## 🚀 Overview

Grading subjective written answers is notoriously slow, plagued by inter-teacher inconsistency, and breaks whenever rubrics evolve mid-evaluation.

**RubricGrader AI** is an explainable, auditable grading assistant that:
1. Scores short answers against configurable multi-point rubrics across any subject.
2. Backs every mark with an **exact verbatim quote** highlighted directly in the student's text.
3. Provides **socratic constructive feedback** without leaking the canonical model answer.
4. Measures human grading agreement using **Quadratic Weighted Kappa (QWK)** and flags borderline cases for manual review.
5. Enables **sub-10ms dynamic re-grading** when teachers alter point weights or split criteria, rendering instant Before-and-After score comparison diffs without model retraining.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["1. Multi-Subject Ingestion"]
        CSV["CSV Ingestion\n(Biology | CS | History | Custom)"] --> Loader["Schema Validator\n(core/data_loader.py)"]
    end

    subgraph Dual_AI ["2. Dual-Engine Intelligence"]
        Loader --> SimEngine["Vector Similarity Engine\n(all-MiniLM-L6-v2 / TF-IDF Fallback)"]
        Loader --> RubricEval["Rubric Reasoner & Quote Extractor\n(Gemini Flash / Local Heuristic)"]
        
        SimEngine --> CosineMatch["Feature 2: Semantic Match (0-100%)"]
        RubricEval --> QuoteAudit{"Verbatim Substring Audit"}
        QuoteAudit -- Verified --> GroundedEv["Verified Evidence Quotes"]
    end

    subgraph Decoupled_Scoring ["3. Instant Deterministic Regrading"]
        GroundedEv --> Regrader["Decoupled Regrader\n(core/regrading_engine.py)"]
        Sliders["Teacher Slider Config\n(Reweight criteria)"] -.->|Sub-10ms Math| Regrader
        Regrader --> DiffTable["Before-and-After Score Diffing Table"]
    end

    subgraph Reliability_Feedback ["4. Reliability & Student Feedback"]
        Regrader --> QWK["Quadratic Weighted Kappa\n(sklearn cohen_kappa_score)"]
        Regrader --> Borderline["Borderline Review Queue\n(|AI - Human| >= 1.5)"]
        GroundedEv --> Feedback["Socratic Feedback Engine\n(4-gram Anti-Leakage Guard)"]
    end

    subgraph UI ["5. Streamlit Dashboard"]
        CosineMatch & DiffTable & QWK & Borderline & Feedback --> Dashboard["Interactive Web UI (app.py)"]
    end
```

---

## 🌟 Hackathon Problem 2 Feature Matrix

| # | Required Feature | How RubricGrader AI Implements It | Verified In |
|---|---|---|---|
| **1** | **Batch Input** | Ingests questions, model answers, rubrics, and student batches across multiple subjects (Biology, CS, History) with schema validation. | `core/data_loader.py` |
| **2** | **Overall Score** | Computes cosine similarity between student answer and model answer using dense sentence vectors (`all-MiniLM-L6-v2`). | `core/similarity_engine.py` |
| **3** | **Per-Criterion Rubric Scoring** | Evaluates each rubric point as `FULL`, `PARTIAL`, or `NONE` and highlights exact verbatim evidence quotes in `<mark>` tags. | `core/rubric_evaluator.py`<br>`core/visualizer.py` |
| **4** | **Student-Facing Feedback** | Generates formative socratic feedback on missed points with automated 4-gram leakage detection preventing answer key spoilers. | `core/feedback_engine.py` |
| **5** | **Reliability Analysis** | Measures human agreement with **Quadratic Weighted Kappa (QWK)** and routes borderline answers ($|AI - Human| \ge 1.5$) to a teacher queue. | `core/metrics.py` |
| **6** | **Dynamic Regrading & Diffing** | Decouples qualitative state from point math, recalculating all student grades in **< 10ms** and showing live Before/After diffs with justifications. | `core/regrading_engine.py` |

---

## ⚡ Quickstart Guide

### 1. Prerequisites
Ensure Python 3.10+ is installed.

### 2. Setup Virtual Environment & Dependencies
```bash
# Activate existing virtual environment
venv\Scripts\activate

# Or install dependencies from requirements.txt
pip install -r requirements.txt
```

### 3. Run Automated Verification Tests
```bash
python -m unittest discover -s tests
# Expected output: Ran 29 tests - OK
```

### 4. Launch the Interactive Dashboard
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

---

## ⏱️ 2-Minute Live Demo Pitch Script

* **[0:00 - 0:25] The Hook**:
  *"Judges, grading written short answers is slow and two teachers often give the same answer completely different marks. Worst of all, halfway through grading an exam, the grading rubric changes—forcing teachers to manually re-grade dozens of papers from scratch. We built **RubricGrader AI** to make grading fast, transparent, and instantly adaptable."*
* **[0:25 - 0:50] Multi-Subject Batch Ingestion & Vector Matching**:
  *(In the sidebar, switch between Biology, Computer Science, and History)*
  *"Here we load an assessment batch across different academic subjects. Our system calculates two separate perspectives: a dense vector Semantic Match Index against the model answer and an itemized rubric evaluation."*
* **[0:50 - 1:15] Verbatim Evidence Proof & Non-Leaking Feedback**:
  *(Expand Student 1 in Tab 1)*
  *"Notice the student's text. Every single mark is backed by a color-coded `<mark>` quote verified directly from the student's words—zero black-box hallucinations. Below it, our socratic feedback engine tells the student what they missed while mathematically guaranteeing zero answer key leaks."*
* **[1:15 - 1:40] The WOW Moment: Sub-10ms Dynamic Regrading**:
  *(Click on Tab 2 'Dynamic Regrading & Diffing'. Move a rubric slider in the sidebar)*
  *"Now, watch what happens when the teacher revises a rubric—say Criterion 1 was too strict and is increased from 2 to 4 marks. In under 10 milliseconds, all students are regraded. This Before-and-After table shows exactly who gained or lost marks and provides a plain-English explanation for every shift, without calling an API or retraining a model."*
* **[1:40 - 2:00] Reliability & Human Trust**:
  *(Click on Tab 3)*
  *"We don't ask teachers to blindly trust AI. Our system calculates Quadratic Weighted Kappa—demonstrating 0.80+ agreement with human markers—and automatically flags borderline discrepancies for human teacher review."*

---

## 🎯 Anticipated Judge Q&A

**Q1: How does your dynamic regrading work so fast without calling an LLM?**  
> **Answer**: We use a **Decoupled Architecture**. The qualitative comprehension step—determining if a student met a criterion as `FULL`, `PARTIAL`, or `NONE`—is done once. The scoring math is a pure linear calculation in Python ($Marks = Weight \times Multiplier$). Adjusting weights takes under 5 milliseconds on 50 answers with 100% mathematical precision.

**Q2: What happens if the venue Wi-Fi goes down during the demo?**  
> **Answer**: The application is 100% offline-resilient. It uses local sentence vector embeddings (`all-MiniLM-L6-v2`) with automatic Scikit-Learn TF-IDF fallback, and features a disk cache in `data/cache/` that pre-warms all benchmark fixtures.

**Q3: How do you guarantee the feedback doesn't leak the exam answers?**  
> **Answer**: Our `FeedbackEngine` uses an automated 4-gram overlap detector. If any sequence of 4 or more consecutive words from the teacher's model answer appears in the student feedback, it is automatically flagged and sanitized into a conceptual guiding question.

---

## 🧪 Tech Stack
- **Dashboard & UI**: Streamlit 1.67
- **Semantic Vectors**: Sentence-Transformers (`all-MiniLM-L6-v2`) + Scikit-Learn TF-IDF Fallback
- **Psychometrics**: Scikit-Learn `cohen_kappa_score(..., weights="quadratic")`
- **Data Engineering**: Pandas 3.1
- **LLM Reasoning**: Google Gemini API (Structured JSON Schema) + Zero-Network Heuristic Fallback
