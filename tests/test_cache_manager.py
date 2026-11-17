"""
tests/test_cache_manager.py
---------------------------
Unit tests verifying persistent disk caching and CSV report export
in core/cache_manager.py.
"""

import os
import unittest
import pandas as pd
from core.cache_manager import CacheManager


class TestCacheManager(unittest.TestCase):

    def setUp(self):
        self.test_cache_file = os.path.join("data", "cache", "test_cache.json")
        self.cache = CacheManager(cache_file=self.test_cache_file)

    def tearDown(self):
        if os.path.exists(self.test_cache_file):
            try:
                os.remove(self.test_cache_file)
            except OSError:
                pass

    def test_save_and_retrieve_cache(self):
        """Test storing and retrieving evaluation results."""
        student_ans = "Cells make ATP from glucose."
        rubric_str = "C1: glucose"
        payload = {"status": "FULL", "total_awarded": 5.0}

        self.cache.save_evaluation(student_ans, rubric_str, payload)
        retrieved = self.cache.get_cached_evaluation(student_ans, rubric_str)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["total_awarded"], 5.0)

    def test_export_graded_csv(self):
        """Test exporting graded DataFrame to valid CSV bytes."""
        df = pd.DataFrame([
            {
                "student_id": "BIO-001",
                "subject": "Biology",
                "question": "What is respiration?",
                "student_answer": "Cells make ATP.",
                "semantic_score_pct": 85.0,
                "rubric_score": 4.5,
                "human_score": 5.0,
                "score_discrepancy": 0.5,
                "is_borderline": False,
                "student_feedback": "Great work."
            }
        ])

        csv_bytes = self.cache.export_graded_csv(df)
        self.assertIsInstance(csv_bytes, bytes)
        csv_str = csv_bytes.decode("utf-8")
        self.assertIn("BIO-001", csv_str)
        self.assertIn("student_feedback", csv_str)

    def test_warm_cache_with_fixtures(self):
        """Test that warming the cache pre-populates sample evaluations."""
        self.cache.warm_cache_with_fixtures()
        self.assertGreater(len(self.cache.cache_data), 0)


if __name__ == "__main__":
    unittest.main()
