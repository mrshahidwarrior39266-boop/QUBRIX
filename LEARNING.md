# RubricGrader AI — Student & Developer Learning Log

Welcome to the project learning log! This document records key concepts, architectural decisions, and troubleshooting steps in plain English so anyone on the team can explain and defend this system to the judges.

---

## 1. Plain-English Glossary

| Term | What it means in plain English | Real-world Analogy |
|---|---|---|
| **Sentence Embedding** | Turning a sentence into a list of numbers (a vector) that captures its core meaning rather than its exact words. | Like a fingerprint of the idea: different words with the same idea have almost identical fingerprints. |
| **Cosine Similarity** | A math equation measuring the angle between two embedding vectors. Ranges from 0.0 (completely unrelated) to 1.0 (identical meaning). | Like two compass needles pointing in the same direction. |
| **Rubric Criterion** | A single grading standard with specific required concepts and maximum marks (e.g., "Explains ATP production: 2 marks"). | Like a checklist item for an inspector. |
| **Verbatim Evidence** | An exact, character-accurate quote copied directly from the student's text proving they fulfilled a criterion. | Like highlighting the quote in a courtroom document to prove a fact. |
| **Quadratic Weighted Kappa (QWK)** | A statistical score (-1.0 to +1.0) measuring agreement between two raters, heavily penalizing large score discrepancies. | If Teacher A gives 5/5 and Teacher B gives 1/5, QWK rings a loud alarm bell. |
| **Decoupled Scoring Engine** | Separating qualitative judgment (Did they answer this? Full/Part/None) from arithmetic (Multiplying points by weights). | Like separating the judge's verdict (guilty/innocent) from the sentencing calculator. Allows instant recalculation without re-trying the case! |

---

## 2. File Map & Data Flow

```
[CSV Datasets] ──> [core/data_loader.py] ──> [core/similarity_engine.py] ──> [Streamlit UI]
(data/sample_*.csv)   (Validates & parses)      (Computes semantic match %)      (Displays results)
```

| File | One-Line Job | Inputs | Outputs |
|---|---|---|---|
| `data/sample_biology.csv` | Synthetic test dataset with questions, rubrics, and student answers | Domain syllabus | Raw tabular data |
| `data/sample_cs.csv` | Computer Science benchmark for testing cross-subject generalization | Domain syllabus | Raw tabular data |
| `data/sample_history.csv` | History benchmark testing humanities reasoning | Domain syllabus | Raw tabular data |
| `core/data_loader.py` | The gatekeeper: loads CSVs, checks required columns, and parses rubrics | Raw CSV file or buffer | Clean Pandas DataFrame & rubric dicts |
| `core/similarity_engine.py` | Vector calculator: computes conceptual similarity against model answer | Student & model text | 0–100% semantic match score |
| `core/rubric_evaluator.py` | Rubric reasoner: assigns FULL/PARTIAL/NONE, awards marks, and verifies verbatim quotes | Question, Model Answer, Rubric, Student Answer | Structured evaluation dictionary with verified quotes |
| `core/feedback_engine.py` | Teacher mentor: synthesizes constructive feedback while protecting answer keys | Rubric evaluation results, Model Answer | Socratic student feedback & leakage audit flag |

---

## 3. Why We Chose X Over Y

* **Why local sentence vectors over LLM prompt for similarity score?**
  Calling an LLM for every similarity score is slow (~1-2 seconds), costs money, and risks rate-limit errors (HTTP 429). Local dense embeddings (`all-MiniLM-L6-v2`) run on CPU in 10 milliseconds, cost $0, and run 100% offline.

* **Why decoupled rubric weights instead of re-prompting the AI?**
  If a teacher changes a rubric slider from 2 marks to 3 marks, asking the AI to grade the whole class again takes 30 seconds and might change previously awarded points randomly. By caching the AI's qualitative decision (`FULL`, `PARTIAL`, `NONE`) and doing the math in Python, re-grading takes under 5 milliseconds with 100% mathematical precision!

* **Why automated 4-gram leakage checking for feedback?**
  A major failure mode of AI graders is accidentally revealing the model answer to the student (e.g. "You should have said: [exact model answer text]"). Our 4-gram overlap detector mathematically scans the generated feedback against the instructor's reference text. If 4 or more identical words appear in a row, the text is flagged and sanitized into a socratic conceptual hint!
