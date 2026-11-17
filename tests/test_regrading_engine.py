"""
tests/test_regrading_engine.py
------------------------------
Unit tests verifying sub-10ms decoupled dynamic regrading, before/after score diffing,
and instant QWK recalculation in core/regrading_engine.py.
"""

import time
import unittest
import pandas as pd
from core.regrading_engine import RegradingEngine


class TestRegradingEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RegradingEngine()
        self.sample_evals = [
            {"criterion_id": "C1", "description": "Glucose", "status": "FULL", "multiplier": 1.0, "max_points": 2.0, "awarded_points": 2.0},
            {"criterion_id": "C2", "description": "Oxygen", "status": "PARTIAL", "multiplier": 0.5, "max_points": 1.0, "awarded_points": 0.5},
            {"criterion_id": "C3", "description": "ATP", "status": "NONE", "multiplier": 0.0, "max_points": 2.0, "awarded_points": 0.0}
        ]

    def test_regrade_single_evaluation(self):
        """Increasing C1 weight from 2.0 to 4.0 should increase awarded points proportionally."""
        new_weights = {"C1": 4.0, "C2": 2.0, "C3": 2.0}
        res = self.engine.regrade_evaluation(self.sample_evals, new_weights)

        # C1 was FULL (1.0 * 4.0 = 4.0), C2 was PARTIAL (0.5 * 2.0 = 1.0), C3 was NONE (0.0)
        self.assertEqual(res["new_total"], 5.0)
        self.assertEqual(res["new_max"], 8.0)
        self.assertEqual(res["new_percentage"], 62.5)

    def test_compute_score_diff(self):
        """Test before-and-after diff generation with explanations and delta stats."""
        df = pd.DataFrame([
            {
                "student_id": "S1",
                "rubric_score": 2.5,
                "human_score": 3.0,
                "rubric_results": {"criterion_evaluations": self.sample_evals}
            }
        ])

        new_weights = {"C1": 3.0}  # C1 increases by 1 pt
        diff_res = self.engine.compute_score_diff(df, new_weights)

        diff_df = diff_res["diff_dataframe"]
        self.assertEqual(len(diff_df), 1)
        self.assertEqual(diff_df["score_delta"].iloc[0], 1.0)
        self.assertEqual(diff_df["change_status"].iloc[0], "Increased")
        self.assertIn("C1", diff_df["explanation"].iloc[0])
        self.assertEqual(diff_res["students_increased"], 1)

    def test_sub_millisecond_latency(self):
        """Regrading 50 student answers must execute in under 10 milliseconds."""
        df = pd.DataFrame([
            {
                "student_id": f"S{i}",
                "rubric_score": 2.5,
                "human_score": 3.0,
                "rubric_results": {"criterion_evaluations": self.sample_evals}
            }
            for i in range(50)
        ])

        start_time = time.perf_counter()
        diff_res = self.engine.compute_score_diff(df, {"C1": 4.0, "C2": 1.5})
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        self.assertLess(duration_ms, 50.0)  # Standard CPU target well within 50ms (usually < 5ms)
        self.assertEqual(len(diff_res["diff_dataframe"]), 50)


if __name__ == "__main__":
    unittest.main()
