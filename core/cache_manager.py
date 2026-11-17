"""
core/cache_manager.py
---------------------
Purpose: Persistent local disk caching for AI evaluations and CSV report export.
         Ensures 100% demo safety and sub-millisecond replay even with zero internet.
Inputs:  Student answers, rubric definitions, and batch evaluation DataFrames.
Outputs: Cached evaluation payloads, disk-persisted JSON, and downloadable CSV byte streams.
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join("data", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "evaluations.json")


class CacheManager:
    """
    Manages persistent local disk caching for evaluated answers.
    Provides offline demo safety and exports graded reports to CSV.
    """

    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self._ensure_cache_dir()
        self.cache_data: Dict[str, Any] = self._load_cache()

    def _ensure_cache_dir(self):
        """Ensure parent directories exist."""
        dirname = os.path.dirname(self.cache_file)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

    def _compute_key(self, student_answer: str, rubric_str: str, context: str = "") -> str:
        """Generate SHA-256 fingerprint for the (answer, rubric, question context) triple.

        Including the question/model-answer context prevents two different assessments
        that happen to share an answer string and rubric from reusing each other's marks.
        """
        content = f"{student_answer.strip()}|||{rubric_str.strip()}|||{context.strip()}".encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk, handling missing or corrupt files gracefully."""
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read cache file ({e}). Starting fresh.")
            return {}

    def _save_to_disk(self):
        """Flush in-memory cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write cache file: {e}")

    def get_cached_evaluation(self, student_answer: str, rubric_str: str, context: str = "") -> Optional[Dict[str, Any]]:
        """Retrieve cached evaluation if available."""
        key = self._compute_key(student_answer, rubric_str, context)
        return self.cache_data.get(key)

    def save_evaluation(self, student_answer: str, rubric_str: str, payload: Dict[str, Any], context: str = ""):
        """Store evaluation in cache and persist to disk."""
        key = self._compute_key(student_answer, rubric_str, context)
        self.cache_data[key] = payload
        self._save_to_disk()

    def export_graded_csv(self, df: pd.DataFrame) -> bytes:
        """
        Export a batch evaluation DataFrame into a clean, downloadable CSV byte stream.
        """
        export_cols = [
            "student_id",
            "subject",
            "question",
            "student_answer",
            "semantic_score_pct",
            "rubric_score",
            "human_score",
            "score_discrepancy",
            "is_borderline",
            "student_feedback"
        ]

        # Only select columns that exist in the DataFrame
        available_cols = [col for col in export_cols if col in df.columns]
        export_df = df[available_cols].copy()

        csv_string = export_df.to_csv(index=False, encoding="utf-8")
        return csv_string.encode("utf-8")

    def warm_cache_with_fixtures(self):
        """
        Pre-evaluate all sample CSVs and store them in the disk cache so that
        the live demo runs instantaneously with zero latency.
        """
        from core.data_loader import DataLoader
        from core.rubric_evaluator import RubricEvaluator
        from core.similarity_engine import SemanticSimilarityEngine
        from core.feedback_engine import FeedbackEngine

        dl = DataLoader()
        sim_engine = SemanticSimilarityEngine(use_fallback=True)
        rubric_eval = RubricEvaluator()
        fb_engine = FeedbackEngine()

        sample_files = [
            os.path.join("data", "sample_biology.csv"),
            os.path.join("data", "sample_cs.csv"),
            os.path.join("data", "sample_history.csv")
        ]

        for path in sample_files:
            if not os.path.exists(path):
                continue
            df = dl.load_csv(path)
            for _, row in df.iterrows():
                sa = str(row["student_answer"])
                rj = str(row["rubric_json"])
                rubric = dl.parse_rubric(rj)
                q = str(row["question"])
                ma = str(row["model_answer"])

                if not self.get_cached_evaluation(sa, rj):
                    eval_res = rubric_eval.evaluate_answer(q, ma, rubric, sa, use_heuristic_fallback=True)
                    self.save_evaluation(sa, rj, eval_res)

        logger.info(f"Cache successfully warmed. Total cached answers: {len(self.cache_data)}")
