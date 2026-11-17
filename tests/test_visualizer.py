"""
tests/test_visualizer.py
------------------------
Unit tests verifying HTML evidence span highlighting and injection safety
in core/visualizer.py.
"""

import unittest
from core.visualizer import highlight_student_evidence


class TestVisualizer(unittest.TestCase):

    def test_highlight_evidence_full_and_partial(self):
        """Quotes must be wrapped with styled <mark> tags and criterion tags."""
        raw_text = "Cells oxidize glucose to generate ATP energy."
        evals = [
            {"criterion_id": "C1", "status": "FULL", "evidence_quote": "oxidize glucose"},
            {"criterion_id": "C2", "status": "PARTIAL", "evidence_quote": "generate ATP energy"}
        ]

        html_out = highlight_student_evidence(raw_text, evals)
        self.assertIn("<mark", html_out)
        self.assertIn("C1: FULL", html_out)
        self.assertIn("C2: PARTIAL", html_out)
        self.assertIn("#d1e7dd", html_out)  # Green
        self.assertIn("#fff3cd", html_out)  # Amber

    def test_empty_quote_handling(self):
        """Unaddressed criteria with empty quotes should leave text unhighlighted."""
        raw_text = "Simple unhighlighted student text."
        evals = [
            {"criterion_id": "C1", "status": "NONE", "evidence_quote": ""}
        ]

        html_out = highlight_student_evidence(raw_text, evals)
        self.assertNotIn("<mark", html_out)
        self.assertIn("Simple unhighlighted student text.", html_out)

    def test_html_injection_safety(self):
        """Dangerous HTML script tags in student input must be escaped."""
        raw_text = "<script>alert('pwned')</script> glucose is metabolized."
        evals = [
            {"criterion_id": "C1", "status": "FULL", "evidence_quote": "glucose is metabolized"}
        ]

        html_out = highlight_student_evidence(raw_text, evals)
        self.assertNotIn("<script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)


if __name__ == "__main__":
    unittest.main()
