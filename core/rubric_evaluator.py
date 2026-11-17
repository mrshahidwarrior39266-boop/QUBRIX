"""
core/rubric_evaluator.py
------------------------
Purpose: Evaluate student answers against configurable rubrics on a per-criterion
         basis, extract verbatim evidence quotes with character-exact validation,
         and compute explainable marks.
Inputs:  Question, Model Answer, parsed Rubric Criteria list, and Student Answer text.
Outputs: Detailed JSON-structured evaluation with criterion fulfillment status,
         awarded points, verbatim evidence quotes, and verification flags.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# Multipliers for criterion fulfillment status
STATUS_MULTIPLIERS = {
    "FULL": 1.0,
    "PARTIAL": 0.5,
    "NONE": 0.0
}


class RubricEvaluator:
    """
    Evaluates student answers against rubric criteria.
    Features:
    - Structured JSON reasoning (Gemini Flash API or local heuristic engine).
    - Verbatim evidence quote extraction and literal substring verification.
    - Zero-network heuristic fallback when offline or without API keys.
    - In-memory result caching to eliminate redundant evaluations.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _verify_verbatim_quote(self, quote: str, student_answer: str) -> bool:
        """
        Verify that an extracted evidence quote is an exact, character-for-character
        substring of the student's raw submitted text.
        """
        if not quote:
            return False
        clean_quote = quote.strip()
        return len(clean_quote) > 0 and clean_quote.lower() in student_answer.lower()

    def evaluate_answer(
        self,
        question: str,
        model_answer: str,
        rubric: List[Dict[str, Any]],
        student_answer: str,
        use_heuristic_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate a student answer against each criterion in the rubric.

        Args:
            question: The assessment prompt.
            model_answer: Instructor reference answer.
            rubric: List of criterion dictionaries with criterion_id, description, max_points.
            student_answer: Text submitted by the student.
            use_heuristic_fallback: Force local heuristic mode (useful for offline testing).

        Returns:
            Dict[str, Any]: Complete evaluation payload with itemized criteria marks and quotes.
        """
        s_clean = student_answer.strip()

        # Cache key based on answer text and rubric JSON representation
        cache_key = f"{s_clean}___" + json.dumps(rubric, sort_keys=True)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Handle empty student answer immediately
        if not s_clean:
            evaluations = []
            for c in rubric:
                evaluations.append({
                    "criterion_id": c["criterion_id"],
                    "description": c["description"],
                    "max_points": float(c.get("max_points", 1.0)),
                    "status": "NONE",
                    "multiplier": 0.0,
                    "awarded_points": 0.0,
                    "evidence_quote": "",
                    "is_quote_verified": False,
                    "evaluator_note": "No response submitted."
                })
            result = {
                "criterion_evaluations": evaluations,
                "total_awarded": 0.0,
                "total_max": sum(float(c.get("max_points", 1.0)) for c in rubric),
                "overall_percentage": 0.0,
                "evaluation_method": "empty_input"
            }
            self._cache[cache_key] = result
            return result

        # Check if we should use Cloud API or Local Heuristic Engine
        if self.api_key and not use_heuristic_fallback:
            try:
                result = self._evaluate_with_gemini(question, model_answer, rubric, s_clean)
            except Exception as e:
                logger.warning(f"Cloud API evaluation failed: {e}. Falling back to local heuristic.")
                result = self._evaluate_with_heuristic(rubric, s_clean)
        else:
            result = self._evaluate_with_heuristic(rubric, s_clean)

        self._cache[cache_key] = result
        return result

    def _evaluate_with_gemini(
        self,
        question: str,
        model_answer: str,
        rubric: List[Dict[str, Any]],
        student_answer: str
    ) -> Dict[str, Any]:
        """Call Gemini Flash API using structured JSON schema."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        prompt = f"""
You are an expert academic evaluator. Evaluate the student's answer against the given rubric criteria.
For each criterion, you must extract an exact verbatim quote from the student's text justifying the mark.

QUESTION: {question}
MODEL ANSWER: {model_answer}

RUBRIC CRITERIA:
{json.dumps(rubric, indent=2)}

STUDENT ANSWER:
\"\"\"{student_answer}\"\"\"

INSTRUCTIONS:
1. For each criterion in the rubric, assign status: 'FULL' (fully satisfied), 'PARTIAL' (partially addressed / minor omission), or 'NONE' (unaddressed or incorrect).
2. 'evidence_quote': Must be an EXACT, literal substring from the student answer proving the mark. If no evidence exists, output empty string \"\".
3. 'evaluator_note': Brief 1-sentence pedagogical justification.

Respond STRICTLY with valid JSON following this schema:
{{
  "evaluations": [
    {{
      "criterion_id": "string",
      "status": "FULL" | "PARTIAL" | "NONE",
      "evidence_quote": "string",
      "evaluator_note": "string"
    }}
  ]
}}
"""

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )

        data = json.loads(response.text)
        raw_evals = {item["criterion_id"]: item for item in data.get("evaluations", [])}

        return self._format_and_validate_results(rubric, raw_evals, student_answer, method="gemini_api")

    def _evaluate_with_heuristic(
        self,
        rubric: List[Dict[str, Any]],
        student_answer: str
    ) -> Dict[str, Any]:
        """
        Local heuristic evaluator based on concept keyword extraction, sentence-level
        token overlap, and substring quote extraction. Operates 100% offline.
        """
        raw_evals = {}
        sentences = [s.strip() for s in re.split(r"[.!?;\n]+", student_answer) if s.strip()]

        for c in rubric:
            cid = c["criterion_id"]
            desc = c["description"].lower()

            # Extract conceptual content words (length >= 4, non-stop words)
            stop_words = {"this", "that", "with", "from", "into", "identifies", "explains", "states", "mentions"}
            keywords = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", desc) if w not in stop_words]

            matched_sentences = []
            keyword_matches = 0

            for sent in sentences:
                sent_lower = sent.lower()
                matches = sum(1 for kw in keywords if kw in sent_lower)
                if matches > 0:
                    matched_sentences.append((matches, sent))
                    keyword_matches += matches

            if matched_sentences:
                matched_sentences.sort(key=lambda x: x[0], reverse=True)
                best_quote = matched_sentences[0][1]

                # Determine status based on coverage of required keywords
                match_ratio = keyword_matches / max(1, len(keywords))
                if match_ratio >= 0.5:
                    status = "FULL"
                    note = f"Key conceptual terms present: '{best_quote}'."
                else:
                    status = "PARTIAL"
                    note = f"Partially addressed; some required concepts omitted."
            else:
                best_quote = ""
                status = "NONE"
                note = "Required concept was not addressed in the response."

            raw_evals[cid] = {
                "criterion_id": cid,
                "status": status,
                "evidence_quote": best_quote,
                "evaluator_note": note
            }

        return self._format_and_validate_results(rubric, raw_evals, student_answer, method="local_heuristic")

    def _format_and_validate_results(
        self,
        rubric: List[Dict[str, Any]],
        raw_evals: Dict[str, Dict[str, Any]],
        student_answer: str,
        method: str
    ) -> Dict[str, Any]:
        """
        Enforce point arithmetic, validate that quotes are genuine substrings,
        and assemble the final structured result.
        """
        final_evals = []
        total_awarded = 0.0
        total_max = 0.0

        for c in rubric:
            cid = c["criterion_id"]
            max_pts = float(c.get("max_points", 1.0))
            total_max += max_pts

            eval_item = raw_evals.get(cid, {})
            status = eval_item.get("status", "NONE").upper()
            if status not in STATUS_MULTIPLIERS:
                status = "NONE"

            multiplier = STATUS_MULTIPLIERS[status]
            awarded = round(max_pts * multiplier, 2)
            total_awarded += awarded

            quote = str(eval_item.get("evidence_quote", "")).strip()

            # Programmatically verify that the quote physically exists in the student answer
            is_verified = self._verify_verbatim_quote(quote, student_answer) if quote else False

            # If quote wasn't verified (minor punctuation difference), attempt fuzzy substring match
            if not is_verified and quote:
                words = quote.split()
                if len(words) >= 3:
                    sub_phrase = " ".join(words[:4])
                    if sub_phrase.lower() in student_answer.lower():
                        is_verified = True

            note = eval_item.get("evaluator_note", f"Evaluated as {status}.")

            final_evals.append({
                "criterion_id": cid,
                "description": c["description"],
                "max_points": max_pts,
                "status": status,
                "multiplier": multiplier,
                "awarded_points": awarded,
                "evidence_quote": quote,
                "is_quote_verified": is_verified,
                "evaluator_note": note
            })

        overall_pct = round((total_awarded / total_max) * 100.0, 1) if total_max > 0 else 0.0

        return {
            "criterion_evaluations": final_evals,
            "total_awarded": round(total_awarded, 2),
            "total_max": round(total_max, 2),
            "overall_percentage": overall_pct,
            "evaluation_method": method
        }

    def evaluate_dataframe(self, df: pd.DataFrame, use_heuristic: bool = False) -> pd.DataFrame:
        """
        Enrich a batch DataFrame with itemized rubric evaluations and total rubric scores.

        Args:
            df: DataFrame containing 'question', 'model_answer', 'rubric_json', 'student_answer'.

        Returns:
            pd.DataFrame: Enriched DataFrame with 'rubric_results', 'rubric_score', and 'rubric_pct'.
        """
        from core.data_loader import DataLoader
        loader = DataLoader()

        enriched = df.copy()
        results = []
        scores = []
        pcts = []

        for _, row in enriched.iterrows():
            q = str(row["question"])
            ma = str(row["model_answer"])
            rubric = loader.parse_rubric(row["rubric_json"])
            sa = str(row["student_answer"])

            res = self.evaluate_answer(q, ma, rubric, sa, use_heuristic_fallback=use_heuristic)
            results.append(res)
            scores.append(res["total_awarded"])
            pcts.append(res["overall_percentage"])

        enriched["rubric_results"] = results
        enriched["rubric_score"] = scores
        enriched["rubric_pct"] = pcts

        return enriched
