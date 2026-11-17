"""
core/feedback_engine.py
-----------------------
Purpose: Generate constructive, socratic student feedback tied to missed rubric points
         without leaking the canonical model answer.
Inputs:  Itemized rubric criterion evaluations and the instructor's model answer.
Outputs: Formative feedback text, missing concept checklist, and anti-leakage audit flag.
"""

import logging
import re
from typing import Any, Dict, List, Optional
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)


class FeedbackEngine:
    """
    Synthesizes socratic, formative feedback for students based on their rubric evaluation.
    Enforces negative-leakage guardrails using n-gram overlap detection to protect exam security.
    """

    def __init__(self, max_leakage_ngram: int = 4):
        self.max_leakage_ngram = max_leakage_ngram

    def check_model_leakage(self, feedback_text: str, model_answer: str) -> bool:
        """
        Audit feedback text against the model answer for leaked phrasing.
        Checks for consecutive n-grams of length >= self.max_leakage_ngram.

        Returns:
            bool: True if safe (no leakage), False if leakage was detected.
        """
        if not feedback_text or not model_answer:
            return True

        # Clean words: lowercase, alphanumeric only
        model_words = re.findall(r"\b[a-zA-Z0-9]+\b", model_answer.lower())
        feedback_words = re.findall(r"\b[a-zA-Z0-9]+\b", feedback_text.lower())

        if len(model_words) < self.max_leakage_ngram or len(feedback_words) < self.max_leakage_ngram:
            return True

        # Generate n-grams from model answer
        model_ngrams = set()
        for i in range(len(model_words) - self.max_leakage_ngram + 1):
            ngram = " ".join(model_words[i:i + self.max_leakage_ngram])
            model_ngrams.add(ngram)

        # Check feedback n-grams
        for j in range(len(feedback_words) - self.max_leakage_ngram + 1):
            fb_ngram = " ".join(feedback_words[j:j + self.max_leakage_ngram])
            if fb_ngram in model_ngrams:
                logger.warning(f"Potential answer key leakage detected on phrase: '{fb_ngram}'")
                return False

        return True

    def generate_feedback(
        self,
        criterion_evaluations: List[Dict[str, Any]],
        model_answer: str = ""
    ) -> Dict[str, Any]:
        """
        Generate constructive, socratic feedback for a student based on their rubric results.

        Args:
            criterion_evaluations: List of criterion dicts from RubricEvaluator.
            model_answer: The reference model answer (used for leakage audit).

        Returns:
            Dict[str, Any]: {
                "feedback": str,
                "missed_criteria": List[str],
                "leak_free": bool
            }
        """
        if not criterion_evaluations:
            return {
                "feedback": "No response evaluated.",
                "missed_criteria": [],
                "leak_free": True
            }

        full_points = []
        partial_points = []
        missing_points = []

        for c in criterion_evaluations:
            cid = c.get("criterion_id", "")
            desc = c.get("description", "")
            status = c.get("status", "NONE").upper()

            if status == "FULL":
                full_points.append((cid, desc))
            elif status == "PARTIAL":
                partial_points.append((cid, desc))
            else:
                missing_points.append((cid, desc))

        # If everything was answered fully
        if not partial_points and not missing_points:
            feedback_body = (
                "Excellent work! You demonstrated complete conceptual mastery across all rubric criteria. "
                "Your explanations were precise and well-supported."
            )
            return {
                "feedback": feedback_body,
                "missed_criteria": [],
                "leak_free": True
            }

        feedback_parts = []

        # Acknowledge strengths first (pedagogical best practice)
        if full_points:
            strengths_str = ", ".join([f"{cid}" for cid, _ in full_points])
            feedback_parts.append(f"Good grasp of {strengths_str}.")

        # Provide constructive socratic hints on partial points
        for cid, desc in partial_points:
            # Extract main concept from description
            concept = self._extract_core_concept(desc)
            feedback_parts.append(
                f"For {cid}: You partially addressed this, but consider expanding further on {concept}. "
                f"How does this concept connect to the core mechanism?"
            )

        # Provide guidance on completely missed points
        for cid, desc in missing_points:
            concept = self._extract_core_concept(desc)
            feedback_parts.append(
                f"For {cid}: Be sure to review and incorporate {concept} in your explanation."
            )

        raw_feedback = " ".join(feedback_parts)

        # Audit against model answer leakage
        is_leak_free = self.check_model_leakage(raw_feedback, model_answer)

        # If leakage was found, sanitize by stripping exact matching words
        if not is_leak_free:
            raw_feedback = (
                "Constructive Feedback: Review the key concepts identified in the rubric. "
                "Ensure you explain both the core mechanism and its functional outcomes in detail."
            )
            is_leak_free = True

        missed_list = [f"{cid}: {desc}" for cid, desc in (partial_points + missing_points)]

        return {
            "feedback": raw_feedback,
            "missed_criteria": missed_list,
            "leak_free": is_leak_free
        }

    def _extract_core_concept(self, description: str) -> str:
        """Helper to extract a friendly conceptual phrase from a rubric description."""
        clean = description.strip()
        # Remove lead verbs like 'Mentions', 'Identifies', 'States', 'Explains'
        clean = re.sub(r"^(mentions|identifies|states|explains|describes|includes)\s+", "", clean, flags=re.I)
        return clean.strip()

    def attach_feedback_to_dataframe(
        self, df: pd.DataFrame, default_model_answer: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Enrich a DataFrame with 'student_feedback', 'missed_criteria', and 'feedback_leak_free'.
        Expects 'rubric_results' column (from RubricEvaluator).
        """
        enriched = df.copy()

        feedbacks = []
        missed = []
        leak_flags = []

        for _, row in enriched.iterrows():
            rubric_res = row.get("rubric_results", {})
            model_ans = row.get("model_answer", default_model_answer or "")

            c_evals = rubric_res.get("criterion_evaluations", []) if isinstance(rubric_res, dict) else []
            fb_res = self.generate_feedback(c_evals, model_answer=str(model_ans))

            feedbacks.append(fb_res["feedback"])
            missed.append(", ".join(fb_res["missed_criteria"]))
            leak_flags.append(fb_res["leak_free"])

        enriched["student_feedback"] = feedbacks
        enriched["missed_criteria"] = missed
        enriched["feedback_leak_free"] = leak_flags

        return enriched
