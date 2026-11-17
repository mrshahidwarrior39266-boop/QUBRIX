"""
tests/test_metrics.py
---------------------
Unit tests verifying Quadratic Weighted Kappa (QWK) calculation,
psychometric tier interpretation, and borderline discrepancy flagging in core/metrics.py.
"""

import unittest
import pandas as pd
from core.metrics import calculate_qwk, flag_borderline_answers


class TestMetrics(unittest.TestCase):

    def test_perfect_qwk(self):
        """Identical human and AI scores must return QWK = 1.0."""
        y_true = [5.0, 4.0, 3.0, 2.0, 0.0]
        y_pred = [5.0, 4.0, 3.0, 2.0, 0.0]
        res = calculate_qwk(y_true, y_pred)
        self.assertEqual(res["qwk_score"], 1.0)
        self.assertEqual(res["interpretation"], "Near Perfect Agreement")
        self.assertEqual(res["mean_absolute_error"], 0.0)

    def test_substantial_agreement_qwk(self):
        """Close adjacent scores (within 1 mark) should yield strong QWK (> 0.70)."""
        y_true = [5.0, 4.0, 3.0, 1.0, 0.0]
        y_pred = [5.0, 4.0, 2.0, 1.0, 0.0]
        res = calculate_qwk(y_true, y_pred)
        self.assertGreater(res["qwk_score"], 0.75)
        self.assertIn(res["interpretation"], ["Substantial Agreement", "Near Perfect Agreement"])

    def test_poor_agreement_qwk(self):
        """Opposite scores must produce very low or negative QWK."""
        y_true = [5.0, 4.0, 3.0, 1.0, 0.0]
        y_pred = [0.0, 1.0, 3.0, 4.0, 5.0]
        res = calculate_qwk(y_true, y_pred)
        self.assertLess(res["qwk_score"], 0.20)

    def test_borderline_flagging(self):
        """Discrepancies >= threshold must be flagged for teacher review."""
        df = pd.DataFrame([
            {"student_id": "S1", "rubric_score": 5.0, "human_score": 2.0},  # diff = 3.0 -> Flag
            {"student_id": "S2", "rubric_score": 4.0, "human_score": 3.5},  # diff = 0.5 -> Pass
            {"student_id": "S3", "rubric_score": 2.0, "human_score": 0.0},  # diff = 2.0 -> Flag
        ])

        flagged = flag_borderline_answers(df, threshold=1.5)
        self.assertTrue(flagged["is_borderline"].iloc[0])
        self.assertFalse(flagged["is_borderline"].iloc[1])
        self.assertTrue(flagged["is_borderline"].iloc[2])
        self.assertEqual(flagged["score_discrepancy"].iloc[0], 3.0)


if __name__ == "__main__":
    unittest.main()
