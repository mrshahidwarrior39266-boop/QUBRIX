"""
tests/test_synonym_engine.py
----------------------------
Unit tests for SynonymEngine (domain acronyms, equivalences, and dense vectors).
"""

import unittest
from core.synonym_engine import SynonymEngine
from core.rubric_evaluator import RubricEvaluator


class TestSynonymEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SynonymEngine()

    def test_domain_thesaurus_biology(self):
        res = self.engine.detect_synonyms(
            student_answer="Cells catabolize glucose to produce ATP energy for cellular work.",
            criterion_description="Mentions breakdown of sugar molecules and cellular energy production",
            subject="Biology"
        )
        self.assertTrue(len(res) >= 1)
        terms = [(r["rubric_term"], r["student_term"]) for r in res]
        self.assertTrue(any("sugar" in t[0] and "glucose" in t[1] for t in terms))

    def test_domain_thesaurus_cs(self):
        res = self.engine.detect_synonyms(
            student_answer="Iteration uses a while loop to repeat execution without stack overflow.",
            criterion_description="Explains loop repetition with constant space",
            subject="Computer Science"
        )
        self.assertTrue(len(res) >= 1)
        terms = [(r["rubric_term"], r["student_term"]) for r in res]
        self.assertTrue(any("iteration" in t[1] or "while loop" in t[1] for t in terms))

    def test_acronym_expansion(self):
        res = self.engine.detect_synonyms(
            student_answer="Mitochondria produce ATP during cellular respiration.",
            criterion_description="States production of adenosine triphosphate or usable energy",
            subject="Biology"
        )
        self.assertTrue(len(res) >= 1)
        self.assertTrue(any(r["student_term"] == "ATP" for r in res))

    def test_rubric_evaluator_synonym_integration(self):
        evaluator = RubricEvaluator()
        rubric = [
            {"criterion_id": "C1", "description": "Mentions breakdown of sugar molecules", "max_points": 2.0},
            {"criterion_id": "C2", "description": "States production of adenosine triphosphate", "max_points": 2.0}
        ]
        res = evaluator.evaluate_answer(
            question="Explain cellular respiration",
            model_answer="Cells break down sugar to produce adenosine triphosphate.",
            rubric=rubric,
            student_answer="Cells catabolize glucose to synthesize ATP.",
            use_heuristic_fallback=True,
            subject="Biology"
        )
        self.assertEqual(len(res["criterion_evaluations"]), 2)
        c1 = res["criterion_evaluations"][0]
        c2 = res["criterion_evaluations"][1]
        self.assertIn("synonym_matches", c1)
        self.assertIn("synonym_matches", c2)
        self.assertTrue(len(c1["synonym_matches"]) > 0)
        self.assertTrue(len(c2["synonym_matches"]) > 0)


if __name__ == "__main__":
    unittest.main()
