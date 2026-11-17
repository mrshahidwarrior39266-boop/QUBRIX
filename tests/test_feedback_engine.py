"""
tests/test_feedback_engine.py
-----------------------------
Unit tests verifying formative feedback synthesis, socratic guidance,
and anti-leakage guardrails in core/feedback_engine.py.
"""

import unittest
import pandas as pd
from core.feedback_engine import FeedbackEngine


class TestFeedbackEngine(unittest.TestCase):

    def setUp(self):
        self.engine = FeedbackEngine(max_leakage_ngram=4)
        self.model_answer = "Cellular respiration oxidizes glucose in the presence of oxygen to produce ATP energy."

    def test_full_credit_feedback(self):
        """Students with all FULL criteria receive praise."""
        c_evals = [
            {"criterion_id": "C1", "description": "Glucose breakdown", "status": "FULL"},
            {"criterion_id": "C2", "description": "Oxygen requirement", "status": "FULL"}
        ]
        res = self.engine.generate_feedback(c_evals, self.model_answer)
        self.assertIn("Excellent work", res["feedback"])
        self.assertEqual(len(res["missed_criteria"]), 0)
        self.assertTrue(res["leak_free"])

    def test_partial_and_missed_feedback(self):
        """Students with missed criteria receive actionable guidance."""
        c_evals = [
            {"criterion_id": "C1", "description": "Mentions glucose breakdown", "status": "FULL"},
            {"criterion_id": "C2", "description": "Identifies oxygen requirement", "status": "NONE"}
        ]
        res = self.engine.generate_feedback(c_evals, self.model_answer)
        self.assertIn("Good grasp of C1", res["feedback"])
        self.assertIn("C2", res["feedback"])
        self.assertIn("oxygen requirement", res["feedback"].lower())
        self.assertEqual(len(res["missed_criteria"]), 1)

    def test_leakage_detection(self):
        """Detect and flag 4-word contiguous model answer leakage."""
        safe_feedback = "Please review aerobic metabolism and how nutrients yield ATP."
        self.assertTrue(self.engine.check_model_leakage(safe_feedback, self.model_answer))

        # Leaked text containing 4 identical consecutive words from model answer:
        # "oxidizes glucose in the"
        leaked_feedback = "Remember that it oxidizes glucose in the cell to make energy."
        self.assertFalse(self.engine.check_model_leakage(leaked_feedback, self.model_answer))

    def test_attach_feedback_to_dataframe(self):
        """Test batch DataFrame feedback attachment."""
        df = pd.DataFrame([
            {
                "model_answer": self.model_answer,
                "rubric_results": {
                    "criterion_evaluations": [
                        {"criterion_id": "C1", "description": "Glucose", "status": "FULL"},
                        {"criterion_id": "C2", "description": "Oxygen", "status": "NONE"}
                    ]
                }
            }
        ])

        enriched = self.engine.attach_feedback_to_dataframe(df)
        self.assertIn("student_feedback", enriched.columns)
        self.assertIn("missed_criteria", enriched.columns)
        self.assertIn("feedback_leak_free", enriched.columns)
        self.assertTrue(enriched["feedback_leak_free"].iloc[0])
        self.assertIn("C2", enriched["student_feedback"].iloc[0])


if __name__ == "__main__":
    unittest.main()
