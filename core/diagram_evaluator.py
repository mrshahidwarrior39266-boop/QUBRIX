"""
core/diagram_evaluator.py
-------------------------
Purpose: Evaluate student diagram submissions against spatial marking points (MPs).
         Extracts 2D bounding boxes [ymin, xmin, ymax, xmax], validates label synonyms,
         and computes explainable visual marks with zero network requirement.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiagramEvaluator:
    """
    Evaluates diagram submissions against discrete spatial marking points.
    Supports both offline deterministic geometric matching and multimodal Gemini inference.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def calculate_box_iou(self, box_a: List[int], box_b: List[int]) -> float:
        """Calculate Intersection over Union (IoU) between two 2D boxes [ymin, xmin, ymax, xmax]."""
        ymin_a, xmin_a, ymax_a, xmax_a = box_a
        ymin_b, xmin_b, ymax_b, xmax_b = box_b

        inter_ymin = max(ymin_a, ymin_b)
        inter_xmin = max(xmin_a, xmin_b)
        inter_ymax = min(ymax_a, ymax_b)
        inter_xmax = min(xmax_a, xmax_b)

        inter_area = max(0, inter_ymax - inter_ymin) * max(0, inter_xmax - inter_xmin)
        area_a = max(0, ymax_a - ymin_a) * max(0, xmax_a - xmin_a)
        area_b = max(0, ymax_b - ymin_b) * max(0, xmax_b - xmin_b)

        union_area = area_a + area_b - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def evaluate_marking_points(
        self,
        student_submission: Dict[str, Any],
        marking_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate a diagram submission against a list of marking points.

        Args:
            student_submission: Dictionary containing:
                - 'diagram_url': URL/path to diagram or SVG
                - 'detected_elements': List of detected labeled regions [ymin, xmin, ymax, xmax, label]
                - 'notes': Student's caption or explanation
            marking_points: List of marking points with expected boxes, labels, and max_points.

        Returns:
            Dict containing itemized marking point evaluations, total score, and visual overlays.
        """
        evaluations = []
        total_awarded = 0.0
        total_max = 0.0

        detected_elements = student_submission.get("detected_elements", [])
        student_notes = student_submission.get("notes", "").lower()

        for mp in marking_points:
            mp_id = mp["mp_id"]
            max_pts = float(mp.get("max_points", 1.0))
            total_max += max_pts

            expected_box = mp.get("expected_box", [100, 100, 900, 900])
            req_labels = [l.lower() for l in mp.get("required_labels", [mp.get("label", "").lower()])]

            # Search for best matching detected element on the student's diagram
            best_iou = 0.0
            best_element = None
            matched_label = None

            for elem in detected_elements:
                elem_box = elem.get("box_2d", [0, 0, 0, 0])
                elem_label = str(elem.get("label", "")).lower()

                # Check label match (exact or synonym)
                label_matches = any(req in elem_label or elem_label in req for req in req_labels)
                if not label_matches and elem_label:
                    # Check if student notes mention the required label
                    label_matches = any(req in student_notes for req in req_labels)

                iou = self.calculate_box_iou(expected_box, elem_box)
                if label_matches:
                    iou += 0.5  # Bonus for label agreement

                if iou > best_iou:
                    best_iou = iou
                    best_element = elem
                    matched_label = elem_label

            # Scoring based on spatial proximity & label detection
            if best_element and best_iou >= 0.4:
                status = "FULL"
                multiplier = 1.0
                box_2d = best_element.get("box_2d", expected_box)
                justification = f"Correctly drawn and labeled '{mp['label']}'."
            elif best_element and best_iou >= 0.15:
                status = "PARTIAL"
                multiplier = 0.5
                box_2d = best_element.get("box_2d", expected_box)
                justification = f"Partially identified '{mp['label']}'; minor spatial/label discrepancy."
            elif any(req in student_notes for req in req_labels):
                status = "PARTIAL"
                multiplier = 0.5
                box_2d = expected_box
                justification = f"Mentioned '{mp['label']}' in diagram legend, but spatial boundary is ambiguous."
            else:
                status = "NONE"
                multiplier = 0.0
                box_2d = expected_box
                justification = f"Missing required marking point: '{mp['label']}'."

            awarded = round(max_pts * multiplier, 2)
            total_awarded += awarded

            evaluations.append({
                "mp_id": mp_id,
                "label": mp.get("label", mp_id),
                "description": mp.get("description", ""),
                "max_points": max_pts,
                "status": status,
                "multiplier": multiplier,
                "awarded_points": awarded,
                "box_2d": box_2d,
                "detected_label": matched_label or "Unlabeled",
                "justification": justification
            })

        overall_pct = round((total_awarded / total_max) * 100.0, 1) if total_max > 0 else 0.0

        return {
            "marking_point_evaluations": evaluations,
            "total_awarded": round(total_awarded, 2),
            "total_max": round(total_max, 2),
            "overall_percentage": overall_pct
        }
