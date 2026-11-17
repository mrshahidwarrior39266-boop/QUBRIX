"""
tests/test_data_loader.py
-------------------------
Unit tests verifying CSV ingestion, schema validation, and rubric parsing
in core/data_loader.py.
"""

import io
import unittest
from core.data_loader import DataLoader, REQUIRED_COLUMNS


class TestDataLoader(unittest.TestCase):

    def setUp(self):
        self.loader = DataLoader()

    def test_load_sample_biology_csv(self):
        """Verify that data/sample_biology.csv loads and validates successfully."""
        df = self.loader.load_csv("data/sample_biology.csv")
        self.assertEqual(len(df), 5)
        for col in REQUIRED_COLUMNS:
            self.assertIn(col, df.columns)
        self.assertIn("human_score", df.columns)
        self.assertEqual(df["subject"].iloc[0], "Biology")

    def test_load_sample_cs_csv(self):
        """Verify that data/sample_cs.csv loads and validates successfully."""
        df = self.loader.load_csv("data/sample_cs.csv")
        self.assertEqual(len(df), 5)
        self.assertEqual(df["subject"].iloc[0], "Computer Science")

    def test_load_sample_history_csv(self):
        """Verify that data/sample_history.csv loads and validates successfully."""
        df = self.loader.load_csv("data/sample_history.csv")
        self.assertEqual(len(df), 5)
        self.assertEqual(df["subject"].iloc[0], "History")

    def test_parse_rubric_valid(self):
        """Test parsing valid JSON rubric strings into structured dictionaries."""
        rubric_json = '[{"criterion_id": "C1", "description": "Explains ATP", "max_points": 2.0}]'
        parsed = self.loader.parse_rubric(rubric_json)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["criterion_id"], "C1")
        self.assertEqual(parsed[0]["max_points"], 2.0)

    def test_parse_rubric_invalid_json(self):
        """Test that malformed JSON raises a clean ValueError."""
        with self.assertRaises(ValueError):
            self.loader.parse_rubric("invalid {json")

    def test_missing_required_column(self):
        """Test that missing required columns raise ValueError."""
        bad_csv = io.StringIO("student_id,subject,question\n1,Math,2+2?")
        with self.assertRaises(ValueError) as ctx:
            self.loader.load_csv(bad_csv)
        self.assertIn("missing required column", str(ctx.exception).lower())

    def test_filter_by_subject(self):
        """Test subject filtering logic."""
        df = self.loader.load_csv("data/sample_biology.csv")
        bio_df = self.loader.filter_by_subject(df, "Biology")
        self.assertEqual(len(bio_df), 5)

        empty_df = self.loader.filter_by_subject(df, "NonexistentSubject")
        self.assertEqual(len(empty_df), 0)

    def test_get_subject_metadata(self):
        """Test extracting canonical question, model answer, and rubric."""
        df = self.loader.load_csv("data/sample_biology.csv")
        q, ma, rubric = self.loader.get_subject_metadata(df, "Biology")
        self.assertTrue("cellular respiration" in q.lower())
        self.assertTrue("glucose" in ma.lower())
        self.assertGreater(len(rubric), 0)


if __name__ == "__main__":
    unittest.main()
