"""
core/data_loader.py
-------------------
Purpose: Ingest, validate, and normalize multi-subject CSV files containing questions,
         model answers, rubrics, and student answers.
Inputs:  CSV file paths or file-like buffer streams (e.g. from Streamlit file uploader).
Outputs: Cleaned pandas DataFrames and parsed rubric criterion dictionaries.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

# Configure logging for friendly diagnostic output
logger = logging.getLogger(__name__)

# Mandatory columns that must exist in any uploaded assessment CSV
REQUIRED_COLUMNS = [
    "student_id",
    "subject",
    "question",
    "model_answer",
    "rubric_json",
    "student_answer",
]

# Optional columns that enhance analysis when present (e.g. for QWK evaluation)
OPTIONAL_COLUMNS = ["human_score", "max_score"]


class DataLoader:
    """
    Handles CSV ingestion, schema validation, and rubric parsing for student answer batches.
    """

    def __init__(self):
        pass

    def load_csv(self, file_source: Union[str, Any]) -> pd.DataFrame:
        """
        Load a CSV file from a path string or file-like buffer, validate its schema,
        and clean up missing or whitespace-only records.

        Args:
            file_source: File path string or file buffer (from open() or st.file_uploader).

        Returns:
            pd.DataFrame: Validated DataFrame with normalized strings.

        Raises:
            ValueError: If required columns are missing or if the CSV is empty.
        """
        # Try UTF-8 first, fallback to latin-1 if Windows encoded
        try:
            df = pd.read_csv(file_source, encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("UTF-8 decoding failed; falling back to latin-1 encoding.")
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            df = pd.read_csv(file_source, encoding="latin-1")

        if df.empty:
            raise ValueError("The provided CSV file contains no data.")

        # Strip whitespace from column names for robust matching
        df.columns = [col.strip().lower() for col in df.columns]

        # Check for mandatory columns
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(missing_cols)}. "
                f"Expected columns: {', '.join(REQUIRED_COLUMNS)}"
            )

        # Clean string columns: replace NaNs with empty string and strip leading/trailing spaces
        text_cols = ["student_id", "subject", "question", "model_answer", "student_answer"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()

        # If human_score exists, cast to numeric (float), defaulting invalid entries to NaN
        if "human_score" in df.columns:
            df["human_score"] = pd.to_numeric(df["human_score"], errors="coerce")

        if "max_score" in df.columns:
            df["max_score"] = pd.to_numeric(df["max_score"], errors="coerce")

        return df

    def parse_rubric(self, rubric_raw: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Parse raw rubric data (JSON string or Python list) into a validated list of
        rubric criterion dictionaries.

        Each criterion dictionary contains:
            - criterion_id (str): Unique tag like 'C1', 'C2'
            - description (str): The expected student knowledge/behavior
            - max_points (float): Point weight for this criterion

        Args:
            rubric_raw: JSON formatted string or list of dicts.

        Returns:
            List[Dict[str, Any]]: Cleaned criterion list.

        Raises:
            ValueError: If rubric JSON is malformed or missing key fields.
        """
        if isinstance(rubric_raw, list):
            criteria = rubric_raw
        elif isinstance(rubric_raw, str):
            rubric_clean = rubric_raw.strip()
            try:
                criteria = json.loads(rubric_clean)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse rubric JSON: {e}")
        else:
            raise ValueError(f"Unsupported rubric format: {type(rubric_raw)}")

        if not isinstance(criteria, list) or len(criteria) == 0:
            raise ValueError("Rubric must be a non-empty list of criteria items.")

        validated_criteria = []
        for idx, item in enumerate(criteria):
            if not isinstance(item, dict):
                raise ValueError(f"Rubric item #{idx + 1} is not a valid dictionary object.")

            cid = str(item.get("criterion_id", f"C{idx + 1}")).strip()
            desc = str(item.get("description", "")).strip()
            
            # Extract point weight, defaulting to 1.0 if unspecified
            try:
                points = float(item.get("max_points", 1.0))
            except (ValueError, TypeError):
                points = 1.0

            if not desc:
                raise ValueError(f"Rubric criterion '{cid}' is missing a description.")

            validated_criteria.append({
                "criterion_id": cid,
                "description": desc,
                "max_points": points
            })

        return validated_criteria

    def get_available_subjects(self, df: pd.DataFrame) -> List[str]:
        """
        Return the list of distinct academic subjects present in the batch.
        """
        if "subject" not in df.columns:
            return []
        return sorted([s for s in df["subject"].unique() if s])

    def filter_by_subject(self, df: pd.DataFrame, subject: str) -> pd.DataFrame:
        """
        Filter the batch DataFrame to only include rows for a specific subject.
        """
        return df[df["subject"] == subject].copy().reset_index(drop=True)

    def get_subject_metadata(
        self, df: pd.DataFrame, subject: Optional[str] = None
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Extract the canonical question, model answer, and parsed rubric for a subject.
        If subject is None, extracts from the first row of the DataFrame.

        Returns:
            Tuple[str, str, List[Dict]]: (question, model_answer, parsed_rubric_list)
        """
        target_df = self.filter_by_subject(df, subject) if subject else df

        if target_df.empty:
            raise ValueError(f"No records found for subject: '{subject}'")

        first_row = target_df.iloc[0]
        question = first_row["question"]
        model_answer = first_row["model_answer"]
        rubric = self.parse_rubric(first_row["rubric_json"])

        return question, model_answer, rubric
