"""
tests/test_diagram_evaluator.py
-------------------------------
Unit tests for DiagramEvaluator (spatial IoU, marking points, and visual scoring).
"""

import unittest
from core.diagram_evaluator import DiagramEvaluator


class TestDiagramEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = DiagramEvaluator()

    def test_iou_calculation(self):
        box1 = [100, 100, 300, 300]
        box2 = [100, 100, 300, 300]
        self.assertAlmostEqual(self.evaluator.calculate_box_iou(box1, box2), 1.0)

        box3 = [500, 500, 700, 700]
        self.assertEqual(self.evaluator.calculate_box_iou(box1, box3), 0.0)

    def test_evaluate_marking_points_full_credit(self):
        mps = [
            {
                "mp_id": "MP-1",
                "label": "Outer Membrane",
                "description": "Continuous outer boundary",
                "max_points": 1.5,
                "expected_box": [60, 80, 880, 920],
                "required_labels": ["outer membrane", "external membrane"]
            },
            {
                "mp_id": "MP-2",
                "label": "Cristae Folds",
                "description": "Inner folded membrane",
                "max_points": 2.0,
                "expected_box": [200, 220, 720, 760],
                "required_labels": ["cristae", "inner membrane folds"]
            }
        ]

        submission = {
            "detected_elements": [
                {"box_2d": [70, 90, 870, 910], "label": "Outer membrane"},
                {"box_2d": [210, 230, 710, 750], "label": "Cristae folds"}
            ],
            "notes": "Mitochondrion structural drawing with membranes and cristae."
        }

        res = self.evaluator.evaluate_marking_points(submission, mps)
        self.assertEqual(len(res["marking_point_evaluations"]), 2)
        self.assertEqual(res["total_awarded"], 3.5)
        self.assertEqual(res["marking_point_evaluations"][0]["status"], "FULL")
        self.assertEqual(res["marking_point_evaluations"][1]["status"], "FULL")

    def test_evaluate_marking_points_missing_element(self):
        mps = [
            {
                "mp_id": "MP-3",
                "label": "Mitochondrial Matrix",
                "max_points": 1.5,
                "expected_box": [350, 350, 650, 650],
                "required_labels": ["matrix", "inner matrix"]
            }
        ]

        submission = {
            "detected_elements": [],
            "notes": "Cell diagram with unlabeled interior."
        }

        res = self.evaluator.evaluate_marking_points(submission, mps)
        self.assertEqual(res["total_awarded"], 0.0)
        self.assertEqual(res["marking_point_evaluations"][0]["status"], "NONE")


if __name__ == "__main__":
    unittest.main()
