"""
core/regrading_engine.py
------------------------
Purpose: Enable sub-10ms dynamic rubric re-grading and before-and-after score diffing
         by decoupling qualitative criterion fulfillment states from mathematical weights.
Inputs:  Evaluated student DataFrames, updated criterion weight configurations, and human ground-truth marks.
Outputs: Regraded scores, Before-and-After score comparison diff tables, per-student explanations,
         and real-time updated QWK psychometric reliability metrics.
"""

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from core.metrics import calculate_qwk

# Configure logging
logger = logging.getLogger(__name__)


class RegradingEngine:
    """
    Decoupled dynamic regrading engine.
    Recalculates scores, grade deltas, and psychometric agreement instantly (sub-10ms)
    without requiring LLM API calls or model retraining.
    """

    def __init__(self):
        pass

    def regrade_evaluation(
        self,
        criterion_evaluations: List[Dict[str, Any]],
        new_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Recalculate an individual student's score against updated rubric weights.

        Args:
            criterion_evaluations: List of criterion evaluations with cached fulfillment status.
            new_weights: Dict mapping criterion_id -> new float point weight.

        Returns:
            Dict[str, Any]: {
                "regraded_evaluations": List[Dict],
                "new_total": float,
                "new_max": float,
                "new_percentage": float
            }
        """
        regraded_evals = []
        new_total = 0.0
        new_max = 0.0

        for c in criterion_evaluations:
            cid = c.get("criterion_id", "")
            orig_max = float(c.get("max_points", 1.0))
            new_w = float(new_weights.get(cid, orig_max))
            new_max += new_w

            # Multiplier preserved from original qualitative judgment:
            # FULL = 1.0, PARTIAL = 0.5, NONE = 0.0
            mult = float(c.get("multiplier", 1.0 if c.get("status") == "FULL" else (0.5 if c.get("status") == "PARTIAL" else 0.0)))
            awarded = round(new_w * mult, 2)
            new_total += awarded

            regraded_c = dict(c)
            regraded_c["max_points"] = new_w
            regraded_c["awarded_points"] = awarded
            regraded_evals.append(regraded_c)

        new_total = round(new_total, 2)
        new_max = round(new_max, 2)
        pct = round((new_total / new_max) * 100.0, 1) if new_max > 0 else 0.0

        return {
            "regraded_evaluations": regraded_evals,
            "new_total": new_total,
            "new_max": new_max,
            "new_percentage": pct
        }

    def regrade_batch(self, df: pd.DataFrame, new_weights: Dict[str, float]) -> pd.DataFrame:
        """
        Apply updated rubric weights across an entire batch DataFrame.
        """
        enriched = df.copy()

        new_scores = []
        new_maxes = []
        new_pcts = []
        new_evals = []

        for _, row in enriched.iterrows():
            rubric_res = row.get("rubric_results", {})
            c_evals = rubric_res.get("criterion_evaluations", []) if isinstance(rubric_res, dict) else []

            regraded = self.regrade_evaluation(c_evals, new_weights)
            new_scores.append(regraded["new_total"])
            new_maxes.append(regraded["new_max"])
            new_pcts.append(regraded["new_percentage"])
            new_evals.append(regraded["regraded_evaluations"])

        enriched["regraded_score"] = new_scores
        enriched["regraded_max"] = new_maxes
        enriched["regraded_pct"] = new_pcts
        enriched["regraded_evaluations"] = new_evals

        return enriched

    def _build_diff_explanation(
        self,
        orig_evals: List[Dict[str, Any]],
        new_evals: List[Dict[str, Any]],
        new_weights: Dict[str, float]
    ) -> str:
        """
        Generate a concise, human-readable justification of why a student's grade changed.
        """
        shifts = []
        orig_map = {c["criterion_id"]: c for c in orig_evals}
        weights_changed = False

        for new_c in new_evals:
            cid = new_c["criterion_id"]
            if cid in orig_map:
                old_c = orig_map[cid]
                old_pts = old_c.get("awarded_points", 0.0)
                new_pts = new_c.get("awarded_points", 0.0)
                diff = round(new_pts - old_pts, 2)

                old_w = old_c.get("max_points", 1.0)
                new_w = new_c.get("max_points", 1.0)
                if abs(float(old_w) - float(new_w)) > 1e-9:
                    weights_changed = True

                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    shifts.append(f"{cid} ({sign}{diff} pts, weight {old_w}→{new_w})")

        if not shifts:
            if weights_changed:
                return "Score unchanged — the revised weights do not affect this student's awarded criteria."
            return "Score unchanged — rubric weights match the original standard."

        return "Adjusted by: " + "; ".join(shifts)

    def compute_score_diff(
        self,
        df: pd.DataFrame,
        new_weights: Dict[str, float],
        human_col: str = "human_score"
    ) -> Dict[str, Any]:
        """
        Generate a complete Before-and-After score diffing report.

        Returns:
            Dict[str, Any]: {
                "diff_dataframe": pd.DataFrame,
                "old_qwk": Dict,
                "new_qwk": Dict,
                "average_delta": float,
                "students_increased": int,
                "students_decreased": int,
                "students_unchanged": int
            }
        """
        regraded_df = self.regrade_batch(df, new_weights)

        student_ids = []
        old_scores = []
        new_scores = []
        deltas = []
        statuses = []
        explanations = []

        for _, row in regraded_df.iterrows():
            sid = row.get("student_id", "N/A")
            old_s = float(row.get("rubric_score", 0.0))
            new_s = float(row.get("regraded_score", 0.0))
            delta = round(new_s - old_s, 2)

            if delta > 0:
                status = "Increased"
            elif delta < 0:
                status = "Decreased"
            else:
                status = "Unchanged"

            rubric_res = row.get("rubric_results", {})
            orig_evals = rubric_res.get("criterion_evaluations", []) if isinstance(rubric_res, dict) else []
            new_evals = row.get("regraded_evaluations", [])
            expl = self._build_diff_explanation(orig_evals, new_evals, new_weights)

            student_ids.append(sid)
            old_scores.append(old_s)
            new_scores.append(new_s)
            deltas.append(delta)
            statuses.append(status)
            explanations.append(expl)

        diff_df = pd.DataFrame({
            "student_id": student_ids,
            "old_score": old_scores,
            "new_score": new_scores,
            "score_delta": deltas,
            "change_status": statuses,
            "explanation": explanations
        })

        # Calculate updated QWK vs human ground truth
        old_qwk = calculate_qwk(regraded_df[human_col], regraded_df["rubric_score"]) if human_col in regraded_df.columns else {}
        new_qwk = calculate_qwk(regraded_df[human_col], regraded_df["regraded_score"]) if human_col in regraded_df.columns else {}

        avg_delta = round(float(np.mean(deltas)), 2) if deltas else 0.0
        n_inc = sum(1 for d in deltas if d > 0)
        n_dec = sum(1 for d in deltas if d < 0)
        n_same = sum(1 for d in deltas if d == 0)

        return {
            "diff_dataframe": diff_df,
            "regraded_batch_df": regraded_df,
            "old_qwk": old_qwk,
            "new_qwk": new_qwk,
            "average_delta": avg_delta,
            "students_increased": n_inc,
            "students_decreased": n_dec,
            "students_unchanged": n_same
        }
