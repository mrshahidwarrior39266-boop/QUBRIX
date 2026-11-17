"""
core/metrics.py
---------------
Purpose: Calculate psychometric agreement measures including Quadratic Weighted Kappa (QWK),
         Mean Absolute Error, and build an automated teacher review queue for borderline answers.
Inputs:  Predicted AI scores, human ground-truth marks, and batch DataFrames.
Outputs: QWK agreement statistics, qualitative reliability tiers, and flagged borderline records.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

# Configure logging
logger = logging.getLogger(__name__)


def calculate_qwk(
    y_true: Union[List[float], np.ndarray, pd.Series],
    y_pred: Union[List[float], np.ndarray, pd.Series],
    min_rating: int = 0,
    max_rating: int = 5,
    bin_step: float = 1.0
) -> Dict[str, Any]:
    """
    Compute the Quadratic Weighted Kappa (QWK) between human ground truth and AI marks.
    Normalizes continuous scores into discrete ordinal tiers so the quadratic penalty matrix
    heavily penalizes distant grading errors (e.g. 5 vs 0) while treating adjacent errors (e.g. 5 vs 4)
    with minor penalties.

    Args:
        y_true: Ground truth scores assigned by human evaluators.
        y_pred: Scores predicted by the automated grading system.
        min_rating: Minimum allowed grade on the rubric scale.
        max_rating: Maximum allowed grade on the rubric scale.
        bin_step: Discretization step (1.0 for integer marks, 0.5 for half-marks).

    Returns:
        Dict[str, Any]: {
            "qwk_score": float,
            "interpretation": str,
            "sample_size": int,
            "mean_absolute_error": float,
            "exact_agreement_pct": float,
            "adjacent_agreement_pct": float
        }
    """
    # Clean and filter pairs where both values are non-null
    clean_pairs = []
    for t, p in zip(y_true, y_pred):
        if pd.notna(t) and pd.notna(p):
            try:
                clean_pairs.append((float(t), float(p)))
            except (ValueError, TypeError):
                continue

    if len(clean_pairs) == 0:
        return {
            "qwk_score": 0.0,
            "interpretation": "Insufficient Data",
            "sample_size": 0,
            "mean_absolute_error": 0.0,
            "exact_agreement_pct": 0.0,
            "adjacent_agreement_pct": 0.0
        }

    trues = np.array([p[0] for p in clean_pairs])
    preds = np.array([p[1] for p in clean_pairs])
    n = len(trues)

    # Kappa is undefined for a single rated submission: report it honestly rather than
    # claiming perfect agreement from one data point.
    if n < 2:
        return {
            "qwk_score": 0.0,
            "interpretation": "Insufficient Data",
            "sample_size": n,
            "mean_absolute_error": round(float(np.mean(np.abs(trues - preds))), 2),
            "exact_agreement_pct": round(float(np.mean(np.abs(trues - preds) < 0.25) * 100.0), 1),
            "adjacent_agreement_pct": round(float(np.mean(np.abs(trues - preds) <= 1.0) * 100.0), 1)
        }

    # Discretize continuous floats to ordinal integer rating categories
    # e.g., for bin_step=1.0: round to nearest integer and clip between min_rating and max_rating
    discretized_true = np.clip(np.round(trues / bin_step), min_rating / bin_step, max_rating / bin_step).astype(int)
    discretized_pred = np.clip(np.round(preds / bin_step), min_rating / bin_step, max_rating / bin_step).astype(int)

    # All possible discrete labels
    all_labels = list(range(int(min_rating / bin_step), int(max_rating / bin_step) + 1))

    # Check for zero variance edge cases
    if len(set(discretized_true)) == 1 and len(set(discretized_pred)) == 1:
        qwk = 1.0 if discretized_true[0] == discretized_pred[0] else 0.0
    else:
        try:
            qwk = float(cohen_kappa_score(
                discretized_true,
                discretized_pred,
                labels=all_labels,
                weights="quadratic"
            ))
            # Handle potential NaN from scikit-learn
            if np.isnan(qwk):
                qwk = 1.0 if np.array_equal(discretized_true, discretized_pred) else 0.0
        except Exception as e:
            logger.warning(f"Error computing cohen_kappa_score: {e}. Defaulting to 0.0.")
            qwk = 0.0

    # Calculate supporting psychometric metrics
    abs_diffs = np.abs(trues - preds)
    mae = float(np.mean(abs_diffs))
    exact_pct = float(np.mean(abs_diffs < 0.25) * 100.0)
    adjacent_pct = float(np.mean(abs_diffs <= 1.0) * 100.0)

    # Interpret QWK scale based on standard Landis & Koch (1977) psychometric thresholds
    if qwk >= 0.80:
        interpretation = "Near Perfect Agreement"
    elif qwk >= 0.60:
        interpretation = "Substantial Agreement"
    elif qwk >= 0.40:
        interpretation = "Moderate Agreement"
    elif qwk >= 0.20:
        interpretation = "Fair Agreement"
    else:
        interpretation = "Slight / Low Agreement"

    return {
        "qwk_score": round(qwk, 4),
        "interpretation": interpretation,
        "sample_size": n,
        "mean_absolute_error": round(mae, 2),
        "exact_agreement_pct": round(exact_pct, 1),
        "adjacent_agreement_pct": round(adjacent_pct, 1)
    }


def flag_borderline_answers(
    df: pd.DataFrame,
    score_col: str = "rubric_score",
    human_col: str = "human_score",
    threshold: float = 1.5
) -> pd.DataFrame:
    """
    Identify student answers where the automated AI score differs substantially from
    the human teacher ground truth, or where grading confidence is borderline.

    Args:
        df: DataFrame containing the scoring results.
        score_col: Column name of AI evaluated score.
        human_col: Column name of human ground truth score.
        threshold: Score difference threshold triggering manual review.

    Returns:
        pd.DataFrame: Enriched copy sorted by discrepancy with review reasons.
    """
    enriched = df.copy()

    if score_col not in enriched.columns or human_col not in enriched.columns:
        enriched["is_borderline"] = False
        enriched["review_reason"] = "Missing comparative score columns."
        enriched["score_discrepancy"] = 0.0
        return enriched

    discrepancies = []
    flags = []
    reasons = []

    for _, row in enriched.iterrows():
        ai_s = row.get(score_col)
        hu_s = row.get(human_col)

        if pd.notna(ai_s) and pd.notna(hu_s):
            diff = round(abs(float(ai_s) - float(hu_s)), 2)
            discrepancies.append(diff)
            if diff >= threshold:
                flags.append(True)
                reasons.append(f"Significant discrepancy: |AI ({ai_s}) - Human ({hu_s})| = {diff} marks (>= {threshold})")
            else:
                flags.append(False)
                reasons.append("High confidence agreement with human grader.")
        else:
            discrepancies.append(0.0)
            flags.append(False)
            reasons.append("No human comparison score provided.")

    enriched["score_discrepancy"] = discrepancies
    enriched["is_borderline"] = flags
    enriched["review_reason"] = reasons

    return enriched
