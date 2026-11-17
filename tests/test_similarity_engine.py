"""
tests/test_similarity_engine.py
-------------------------------
Unit tests verifying semantic vector similarity calculation, batch scoring,
and TF-IDF fallback behavior in core/similarity_engine.py.
"""

import unittest
import pandas as pd
from core.similarity_engine import SemanticSimilarityEngine


class TestSimilarityEngine(unittest.TestCase):

    def setUp(self):
        # Force TF-IDF fallback for fast, deterministic unit test verification
        self.engine = SemanticSimilarityEngine(use_fallback=True)

    def test_identical_answers(self):
        """Identical answers must return a similarity of 1.0."""
        text = "Photosynthesis produces glucose from sunlight."
        sim = self.engine.compute_similarity(text, text)
        self.assertAlmostEqual(sim, 1.0, places=4)

    def test_empty_answers(self):
        """Empty or whitespace-only answers must return 0.0."""
        sim = self.engine.compute_similarity("", "Model answer")
        self.assertEqual(sim, 0.0)

        sim2 = self.engine.compute_similarity("   ", "   ")
        self.assertEqual(sim2, 0.0)

    def test_paraphrase_similarity(self):
        """Answers expressing the same meaning should have significant similarity."""
        student = "Cells break down glucose using oxygen to create ATP energy."
        model = "Cellular respiration oxidizes glucose in the presence of oxygen to produce ATP."
        sim = self.engine.compute_similarity(student, model)
        # Even with keyword-based TF-IDF fallback, shared terms (glucose, oxygen, ATP) yield positive similarity
        self.assertGreater(sim, 0.10)

    def test_unrelated_answers(self):
        """Completely unrelated answers should have low similarity."""
        student = "The French Revolution began in 1789 with the storming of the Bastille."
        model = "Cellular respiration produces ATP energy from glucose and oxygen."
        sim = self.engine.compute_similarity(student, model)
        self.assertLess(sim, 0.20)

    def test_batch_compute(self):
        """Batch compute must return scores matching the number of input answers."""
        students = [
            "Cells make ATP from glucose",
            "Breathing lungs oxygen",
            "Ancient Roman architecture"
        ]
        model = "Cellular respiration synthesizes ATP from glucose"
        scores = self.engine.batch_compute_similarity(students, model)
        self.assertEqual(len(scores), 3)
        # First student is closest to model
        self.assertGreater(scores[0], scores[2])

    def test_score_dataframe(self):
        """Verify that score_dataframe enriches a DataFrame with all required columns."""
        df = pd.DataFrame([
            {
                "student_id": "S1",
                "student_answer": "Cells break down sugar for ATP.",
                "model_answer": "Cellular respiration oxidizes glucose to generate ATP."
            },
            {
                "student_id": "S2",
                "student_answer": "Unrelated history text.",
                "model_answer": "Cellular respiration oxidizes glucose to generate ATP."
            }
        ])
        scored_df = self.engine.score_dataframe(df)
        self.assertIn("semantic_similarity", scored_df.columns)
        self.assertIn("semantic_score_pct", scored_df.columns)
        self.assertIn("semantic_band", scored_df.columns)
        self.assertGreater(scored_df["semantic_score_pct"].iloc[0], scored_df["semantic_score_pct"].iloc[1])


if __name__ == "__main__":
    unittest.main()
