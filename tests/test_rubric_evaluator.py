"""
tests/test_rubric_evaluator.py
------------------------------
Unit tests verifying per-criterion rubric evaluation, verbatim evidence quote extraction,
and substring validation in core/rubric_evaluator.py.
"""

import unittest
import pandas as pd
from core.rubric_evaluator import RubricEvaluator


class TestRubricEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = RubricEvaluator()
        self.question = "Explain cellular respiration."
        self.model_answer = "Cells break down glucose using oxygen to produce ATP energy."
        self.rubric = [
            {"criterion_id": "C1", "description": "Mentions breakdown of glucose or sugar", "max_points": 2.0},
            {"criterion_id": "C2", "description": "Identifies oxygen requirement", "max_points": 1.0},
            {"criterion_id": "C3", "description": "States production of ATP energy", "max_points": 2.0}
        ]

    def test_evaluate_full_credit(self):
        """Answer covering all points receives full status and verified quotes."""
        student = "Cells break down glucose using oxygen to synthesize ATP energy."
        res = self.evaluator.evaluate_answer(
            self.question, self.model_answer, self.rubric, student, use_heuristic_fallback=True
        )

        self.assertEqual(len(res["criterion_evaluations"]), 3)
        self.assertGreater(res["total_awarded"], 3.0)

        # Verify quote exists physically in student answer
        for c_eval in res["criterion_evaluations"]:
            if c_eval["evidence_quote"]:
                self.assertTrue(c_eval["is_quote_verified"])
                self.assertIn(c_eval["evidence_quote"].lower(), student.lower())

    def test_evaluate_empty_answer(self):
        """Empty student submission receives 0 marks and status NONE."""
        res = self.evaluator.evaluate_answer(
            self.question, self.model_answer, self.rubric, "", use_heuristic_fallback=True
        )
        self.assertEqual(res["total_awarded"], 0.0)
        self.assertEqual(res["overall_percentage"], 0.0)
        for c in res["criterion_evaluations"]:
            self.assertEqual(c["status"], "NONE")
            self.assertEqual(c["awarded_points"], 0.0)

    def test_verbatim_validation_logic(self):
        """Directly test quote validation method."""
        raw_text = "Photosynthesis requires chlorophyll and sunlight."
        valid_quote = "chlorophyll and sunlight"
        invalid_quote = "mitochondria and glucose"

        self.assertTrue(self.evaluator._verify_verbatim_quote(valid_quote, raw_text))
        self.assertFalse(self.evaluator._verify_verbatim_quote(invalid_quote, raw_text))

    def test_evaluate_dataframe(self):
        """Test batch DataFrame scoring."""
        from core.data_loader import DataLoader
        dl = DataLoader()
        df = dl.load_csv("data/sample_biology.csv")

        scored_df = self.evaluator.evaluate_dataframe(df, use_heuristic=True)
        self.assertIn("rubric_results", scored_df.columns)
        self.assertIn("rubric_score", scored_df.columns)
        self.assertIn("rubric_pct", scored_df.columns)
        self.assertEqual(len(scored_df), 5)
        # Highest score should exceed lowest score
        self.assertGreater(scored_df["rubric_score"].max(), scored_df["rubric_score"].min())


if __name__ == "__main__":
    unittest.main()
