"""
backend_api.py
--------------
High-performance FastAPI backend bridging the RubricGrader AI core engine
with the Cyber-Studio React + Three.js WebGL frontend.
"""

import html as html_lib
import io
import json
import math
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure workspace root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.cache_manager import CacheManager
from core.data_loader import DataLoader
from core.feedback_engine import FeedbackEngine
from core.metrics import calculate_qwk, flag_borderline_answers
from core.regrading_engine import RegradingEngine
from core.rubric_evaluator import RubricEvaluator
from core.similarity_engine import SemanticSimilarityEngine

app = FastAPI(
    title="RubricGrader AI - Cyber-Studio API",
    description="Explainable, Sub-10ms Rubric Evaluation Engine with Three.js Visualizer",
    version="2.1.0"
)

# Enable CORS for local dev / browser requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
loader = DataLoader()
# Real dense sentence embeddings (all-MiniLM-L6-v2, cached locally) with automatic
# TF-IDF lexical fallback if the model is unavailable. The API reports which engine
# is actually active so the UI never overstates the metric.
sim_engine = SemanticSimilarityEngine()
evaluator = RubricEvaluator()
feedback_engine = FeedbackEngine()
regrading_engine = RegradingEngine()
cache_mgr = CacheManager()
cache_mgr.warm_cache_with_fixtures()

# Pre-defined benchmark subjects mapping
PRESET_DATASETS = {
    "biology": {
        "id": "biology",
        "name": "Cellular Respiration (Biology)",
        "subject": "Biology",
        "file": os.path.join("data", "sample_biology.csv"),
        "subject_filter": "Biology"
    },
    "cs": {
        "id": "cs",
        "name": "Recursion vs Iteration (Computer Science)",
        "subject": "Computer Science",
        "file": os.path.join("data", "sample_cs.csv"),
        "subject_filter": "Computer Science"
    },
    "history": {
        "id": "history",
        "name": "Industrial Revolution (History)",
        "subject": "History",
        "file": os.path.join("data", "sample_history.csv"),
        "subject_filter": "History"
    },
}

# In-memory storage for active uploaded custom dataset
custom_uploaded_df: Optional[pd.DataFrame] = None
custom_uploaded_name: Optional[str] = None

# Baseline evaluation cache: dataset key -> {"payload": dict, "df": DataFrame}
# The expensive qualitative pass (rubric reasoning + feedback) runs once per dataset;
# regrading then only performs the deterministic O(n) weight arithmetic.
BASELINE_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = threading.Lock()
CACHE_GENERATION = 0  # bumped whenever a custom upload replaces the active dataset


def _semantic_engine_label() -> str:
    """Human-readable name of the similarity engine actually in use."""
    return "sentence-transformers" if sim_engine.engine_type == "sentence-transformers" else "tfidf"


def _insufficient_qwk(sample_size: int = 0) -> Dict[str, Any]:
    """QWK is undefined below two rated submissions; report it honestly."""
    return {
        "qwk_score": 0.0,
        "interpretation": "Insufficient Data",
        "sample_size": sample_size,
        "mean_absolute_error": 0.0,
        "exact_agreement_pct": 0.0,
        "adjacent_agreement_pct": 0.0
    }


def _compute_confidence(
    criterion_evaluations: List[Dict[str, Any]],
    semantic_similarity: float,
    human_score: Optional[float],
    ai_score: float
) -> Dict[str, Any]:
    """Score how much a teacher should trust one automated mark, with plain-English reasons.

    Signals: unverified evidence quotes, weak semantic alignment, and disagreement with
    the human benchmark. The same rules are mirrored in the UI so displayed values stay live.
    """
    score = 100.0
    reasons: List[str] = []

    unverified = [
        c for c in criterion_evaluations
        if c.get("evidence_quote") and not c.get("is_quote_verified")
    ]
    if unverified:
        score -= min(30.0, 15.0 * len(unverified))
        reasons.append(
            f"{len(unverified)} evidence quote{'s' if len(unverified) > 1 else ''} could not be verified verbatim"
        )

    if semantic_similarity < 0.45:
        score -= 15.0
        reasons.append("Answer is only loosely aligned with the reference answer")

    if human_score is not None:
        gap = abs(float(ai_score) - float(human_score))
        if gap >= 1.5:
            score -= 30.0
            reasons.append(f"AI–human gap of {gap:.2f} marks")
        elif gap >= 1.0:
            score -= 12.0
            reasons.append(f"AI–human gap of {gap:.2f} marks")

    score = max(0.0, min(100.0, round(score)))
    label = "High" if score >= 80 else "Medium" if score >= 55 else "Low"
    if not reasons:
        reasons.append("All evidence verified and marks align with the human benchmark")

    return {"score": score, "label": label, "reasons": reasons}


def _quote_verification_stats(df_scored: pd.DataFrame) -> Tuple[int, int, float]:
    """Count how many awarded evidence quotes are genuinely verbatim."""
    verified = 0
    total = 0
    for _, row in df_scored.iterrows():
        res = row.get("rubric_results", {})
        for c in res.get("criterion_evaluations", []) if isinstance(res, dict) else []:
            if c.get("evidence_quote"):
                total += 1
                if c.get("is_quote_verified"):
                    verified += 1
    pct = round((verified / total) * 100.0, 1) if total else 100.0
    return verified, total, pct


def compute_assessment(df_raw: pd.DataFrame, subject_name: str) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Execute the complete scoring and evaluation pipeline on a filtered DataFrame.

    Returns the JSON payload plus the enriched DataFrame (reused for cached regrading).
    """
    if df_raw is None or len(df_raw) == 0:
        raise ValueError("No submissions found for this assessment.")

    question, model_answer, parsed_rubric = loader.get_subject_metadata(df_raw)
    max_pts = float(sum(c["max_points"] for c in parsed_rubric))

    # 1. Semantic Similarity (dense vectors when available)
    df_scored = sim_engine.score_dataframe(df_raw)

    # 2. Rubric Evaluation with cached lookups
    eval_results = []
    rubric_scores = []
    rubric_pcts = []
    for _, row in df_scored.iterrows():
        sa = str(row["student_answer"])
        rj = str(row.get("rubric_json", ""))
        cache_context = f"{question}|||{model_answer}"
        cached = cache_mgr.get_cached_evaluation(sa, rj, context=cache_context)
        if cached:
            res = cached
        else:
            res = evaluator.evaluate_answer(
                question, model_answer, parsed_rubric, sa, use_heuristic_fallback=True
            )
            cache_mgr.save_evaluation(sa, rj, res, context=cache_context)
        eval_results.append(res)
        rubric_scores.append(res["total_awarded"])
        rubric_pcts.append(res["overall_percentage"])

    df_scored["rubric_results"] = eval_results
    df_scored["rubric_score"] = rubric_scores
    df_scored["rubric_pct"] = rubric_pcts

    # 3. Feedback attachment (socratic + leakage audit)
    df_scored = feedback_engine.attach_feedback_to_dataframe(df_scored, default_model_answer=model_answer)

    # 4. Borderline review flagging (gracefully skips when human marks are absent)
    df_scored = flag_borderline_answers(df_scored, score_col="rubric_score", human_col="human_score", threshold=1.5)

    # 5. Metrics
    total_submissions = int(len(df_scored))
    avg_sim = round(float(df_scored["semantic_score_pct"].mean()), 1) if total_submissions else 0.0
    avg_rubric = round(float(df_scored["rubric_score"].mean()), 2) if total_submissions else 0.0

    if "human_score" in df_scored.columns and int(df_scored["human_score"].notna().sum()) >= 2:
        qwk_info = calculate_qwk(
            df_scored["human_score"],
            df_scored["rubric_score"],
            max_rating=max(1, int(math.ceil(max_pts)))
        )
    else:
        qwk_info = _insufficient_qwk(int(df_scored["human_score"].notna().sum()) if "human_score" in df_scored.columns else 0)

    verified, total_quotes, verify_pct = _quote_verification_stats(df_scored)

    # Prepare students payload (marks + explainable confidence signals)
    students_payload = []
    confidence_scores: List[float] = []
    low_confidence_count = 0
    needs_review_count = 0

    for _, r in df_scored.iterrows():
        evals = r["rubric_results"].get("criterion_evaluations", [])
        human_value = float(r["human_score"]) if pd.notnull(r.get("human_score")) else None
        confidence = _compute_confidence(
            evals, float(r["semantic_similarity"]), human_value, float(r["rubric_score"])
        )
        needs_review = bool(r.get("is_borderline", False)) or confidence["label"] == "Low"
        confidence_scores.append(confidence["score"])
        if confidence["label"] == "Low":
            low_confidence_count += 1
        if needs_review:
            needs_review_count += 1

        students_payload.append({
            "student_id": str(r["student_id"]),
            "student_answer": str(r["student_answer"]),
            "human_score": human_value,
            "semantic_score_pct": float(r["semantic_score_pct"]),
            "semantic_similarity": float(r["semantic_similarity"]),
            "semantic_band": str(r["semantic_band"]),
            "rubric_score": float(r["rubric_score"]),
            "rubric_pct": float(r["rubric_pct"]),
            "rubric_results": evals,
            "feedback": str(r.get("student_feedback", "")),
            "leak_free": bool(r.get("feedback_leak_free", True)),
            "is_borderline": bool(r.get("is_borderline", False)),
            "score_discrepancy": float(r.get("score_discrepancy", 0.0)),
            "confidence_score": confidence["score"],
            "confidence_label": confidence["label"],
            "confidence_reasons": confidence["reasons"],
            "needs_review": needs_review
        })

    payload = {
        "subject": subject_name,
        "question": question,
        "model_answer": model_answer,
        "rubric": parsed_rubric,
        "students": students_payload,
        "metrics": {
            "total_submissions": total_submissions,
            "avg_semantic_match": avg_sim,
            "avg_rubric_score": avg_rubric,
            "max_possible_score": round(max_pts, 2),
            "qwk_score": qwk_info["qwk_score"],
            "qwk_interpretation": qwk_info["interpretation"],
            "mae": qwk_info.get("mean_absolute_error", 0.0),
            "exact_agreement_pct": qwk_info.get("exact_agreement_pct", 0.0),
            "adjacent_agreement_pct": qwk_info.get("adjacent_agreement_pct", 0.0),
            "borderline_count": int(df_scored["is_borderline"].sum()),
            "needs_review_count": needs_review_count,
            "low_confidence_count": low_confidence_count,
            "avg_confidence": round(float(sum(confidence_scores) / len(confidence_scores)), 1) if confidence_scores else 0.0,
            "semantic_engine": _semantic_engine_label(),
            "verified_quotes": verified,
            "total_quotes": total_quotes,
            "quote_verification_pct": verify_pct
        }
    }
    return payload, df_scored


def _resolve_dataset(dataset_id: str) -> Tuple[pd.DataFrame, str, str]:
    """Resolve a dataset id to (filtered DataFrame, subject name, cache key)."""
    if dataset_id.startswith("custom:"):
        if custom_uploaded_df is None:
            raise HTTPException(status_code=404, detail="No custom CSV is loaded on the server. Upload a file first.")
        subj = dataset_id.replace("custom:", "", 1)
        filtered = loader.filter_by_subject(custom_uploaded_df, subj)
        if filtered.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Subject '{subj}' is not part of the currently uploaded file. Re-select an available dataset."
            )
        return filtered, subj, f"custom:{subj}:{CACHE_GENERATION}"

    if dataset_id not in PRESET_DATASETS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'.")

    preset = PRESET_DATASETS[dataset_id]
    try:
        df_raw = loader.load_csv(preset["file"])
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Could not load benchmark file: {exc}")
    filtered = loader.filter_by_subject(df_raw, preset["subject_filter"])
    return filtered, preset["subject_filter"], f"preset:{dataset_id}"


def _get_baseline(dataset_id: str) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Return the cached baseline payload + scored DataFrame, computing it once."""
    df_raw, subject, cache_key = _resolve_dataset(dataset_id)
    with CACHE_LOCK:
        cached = BASELINE_CACHE.get(cache_key)
    if cached:
        return cached["payload"], cached["df"]

    try:
        payload, df_scored = compute_assessment(df_raw, subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    with CACHE_LOCK:
        BASELINE_CACHE[cache_key] = {"payload": payload, "df": df_scored}
    return payload, df_scored


def _sanitize_weights(raw: Dict[str, float], rubric: List[Dict[str, Any]]) -> Dict[str, float]:
    """Validate client-supplied rubric weights and return the fully resolved set."""
    resolved: Dict[str, float] = {}
    for c in rubric:
        cid = c["criterion_id"]
        default = float(c.get("max_points", 1.0))
        value = raw.get(cid, default)
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Weight for {cid} must be a number.")
        if not math.isfinite(value):
            raise HTTPException(status_code=400, detail=f"Weight for {cid} must be a finite number.")
        if value < 0:
            raise HTTPException(status_code=400, detail=f"Weight for {cid} cannot be negative.")
        if value > 1000:
            raise HTTPException(status_code=400, detail=f"Weight for {cid} is unrealistically large (max 1000).")
        resolved[cid] = round(value, 2)
    return resolved


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "engine": "RubricGrader AI Cyber-Studio",
        "semantic_engine": _semantic_engine_label(),
        "cache_entries": len(cache_mgr.cache_data),
        "cached_datasets": len(BASELINE_CACHE),
        "custom_dataset": custom_uploaded_name,
        "version": "2.1.0"
    }


@app.get("/api/datasets")
def list_datasets():
    datasets = [
        {"id": k, "name": v["name"], "subject": v.get("subject"), "type": "preset"}
        for k, v in PRESET_DATASETS.items()
    ]
    if custom_uploaded_df is not None:
        custom_subjects = loader.get_available_subjects(custom_uploaded_df)
        for cs in custom_subjects:
            datasets.append({
                "id": f"custom:{cs}",
                "name": f"📁 Custom: {cs}",
                "type": "custom"
            })
    return {"datasets": datasets, "semantic_engine": _semantic_engine_label()}


@app.get("/api/assessment")
def get_assessment(dataset_id: str = Query(default="biology")):
    payload, _ = _get_baseline(dataset_id)
    return payload


class RegradeRequest(BaseModel):
    dataset_id: str
    slider_weights: Dict[str, float]


@app.post("/api/regrade")
def regrade_assessment(req: RegradeRequest):
    t_request = time.perf_counter()
    payload, df_baseline = _get_baseline(req.dataset_id)

    weights = _sanitize_weights(req.slider_weights, payload["rubric"])
    human_col = "human_score" if "human_score" in df_baseline.columns else "__no_human__"

    # Deterministic recalculation only: no re-evaluation, no API calls.
    t_start = time.perf_counter()
    diff_report = regrading_engine.compute_score_diff(df_baseline, weights, human_col=human_col)
    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    diff_df = diff_report["diff_dataframe"]
    diff_rows = []
    for _, r in diff_df.iterrows():
        diff_rows.append({
            "student_id": str(r["student_id"]),
            "old_score": float(r["old_score"]),
            "new_score": float(r["new_score"]),
            "score_delta": float(r["score_delta"]),
            "change_status": str(r["change_status"]),
            "explanation": str(r["explanation"])
        })

    human_profile = {}
    for s in payload["students"]:
        human_profile[s["student_id"]] = {
            "human_score": s["human_score"],
            "semantic_score_pct": s["semantic_score_pct"]
        }

    rows = []
    for row in diff_rows:
        info = human_profile.get(row["student_id"], {})
        human = info.get("human_score")
        rows.append({
            **row,
            "human_score": human,
            "score_discrepancy": round(abs(row["new_score"] - human), 2) if human is not None else None
        })

    def _normalised_qwk(info):
        if not info:
            return _insufficient_qwk()
        normalised = dict(info)
        normalised.setdefault("qwk_interpretation", normalised.get("interpretation", "—"))
        return normalised

    new_qwk = _normalised_qwk(diff_report.get("new_qwk"))
    old_qwk = _normalised_qwk(diff_report.get("old_qwk"))

    return {
        "diff_rows": rows,
        "old_qwk": old_qwk,
        "new_qwk": new_qwk,
        "new_max_score": round(sum(weights.values()), 2),
        "new_avg_score": round(float(diff_df["new_score"].mean()), 2) if len(diff_df) else 0.0,
        "recalculation_latency_ms": latency_ms,
        "request_latency_ms": round((time.perf_counter() - t_request) * 1000, 2),
        "weights_applied": weights
    }


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global custom_uploaded_df, custom_uploaded_name, CACHE_GENERATION

    filename = (file.filename or "upload.csv").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    try:
        content = await file.read()
        if not content.strip():
            raise ValueError("The uploaded file is empty.")
        if len(content) > 8 * 1024 * 1024:
            raise ValueError("File is larger than the 8 MB limit.")
        buffer = io.BytesIO(content)
        df_parsed = loader.load_csv(buffer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}")

    if len(df_parsed) > 5000:
        raise HTTPException(status_code=413, detail="Batch too large: maximum 5,000 submissions per file.")

    subjects = loader.get_available_subjects(df_parsed)
    if not subjects:
        raise HTTPException(status_code=400, detail="The CSV does not contain any usable subject values.")

    # Validate every subject's rubric up front so a broken file can never reach the dashboard.
    for subj in subjects:
        try:
            loader.get_subject_metadata(df_parsed, subj)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid rubric for subject '{subj}': {exc}")

    custom_uploaded_df = df_parsed
    custom_uploaded_name = filename
    CACHE_GENERATION += 1
    with CACHE_LOCK:
        BASELINE_CACHE.clear()

    return {
        "success": True,
        "filename": filename,
        "rows_count": int(len(df_parsed)),
        "subjects": subjects,
        "default_subject": subjects[0]
    }


@app.delete("/api/custom_dataset")
@app.post("/api/custom_dataset/clear")
def clear_custom_dataset():
    global custom_uploaded_df, custom_uploaded_name, CACHE_GENERATION
    custom_uploaded_df = None
    custom_uploaded_name = None
    CACHE_GENERATION += 1
    with CACHE_LOCK:
        BASELINE_CACHE.clear()
    return {"success": True, "message": "Custom dataset removed."}


def _parse_weights_param(weights: Optional[str], rubric: List[Dict[str, Any]]) -> Dict[str, float]:
    if not weights:
        return _sanitize_weights({}, rubric)
    try:
        raw = json.loads(weights)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="The 'weights' parameter must be a JSON object.")
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="The 'weights' parameter must be a JSON object.")
    return _sanitize_weights(raw, rubric)


@app.get("/api/export_csv")
def export_csv(
    dataset_id: str = Query(default="biology"),
    weights: Optional[str] = Query(default=None),
    reviewed: Optional[str] = Query(default=None, description="Comma-separated approved student IDs")
):
    payload, df_baseline = _get_baseline(dataset_id)
    applied_weights = _parse_weights_param(weights, payload["rubric"])
    reviewed_ids = {s.strip() for s in (reviewed or "").split(",") if s.strip()}

    df_regraded = regrading_engine.regrade_batch(df_baseline, applied_weights)
    student_meta = {s["student_id"]: s for s in payload["students"]}
    rubric_ids = [c["criterion_id"] for c in payload["rubric"]]

    export_rows = []
    for _, r in df_regraded.iterrows():
        sid = str(r["student_id"])
        meta = student_meta.get(sid, {})
        new_score = float(r["regraded_score"])
        human = meta.get("human_score")
        discrepancy = round(abs(new_score - human), 2) if human is not None else None

        regraded_evals = r.get("regraded_evaluations", [])
        eval_map = {c.get("criterion_id"): c for c in regraded_evals}
        confidence = _compute_confidence(
            regraded_evals, float(r["semantic_similarity"]), human, new_score
        )
        needs_review = bool(discrepancy is not None and discrepancy >= 1.5) or confidence["label"] == "Low"

        row = {
            "student_id": sid,
            "student_answer": r["student_answer"],
            "baseline_score": round(float(r["rubric_score"]), 2),
            "rubric_score": round(new_score, 2),
            "max_score": round(float(r["regraded_max"]), 2),
            "rubric_pct": float(r["regraded_pct"]),
            "human_score": human if human is not None else "",
            "score_discrepancy": discrepancy if discrepancy is not None else "",
            "semantic_score_pct": float(r["semantic_score_pct"]),
            "semantic_band": r.get("semantic_band", ""),
            "confidence_score": confidence["score"],
            "confidence_label": confidence["label"],
            "confidence_reasons": "; ".join(confidence["reasons"]),
            "needs_review": needs_review,
            "teacher_reviewed": sid in reviewed_ids,
            "feedback": meta.get("feedback", ""),
            "leak_free": meta.get("leak_free", True)
        }

        for cid in rubric_ids:
            c = eval_map.get(cid, {})
            row[f"{cid}_status"] = c.get("status", "")
            row[f"{cid}_awarded"] = round(float(c.get("awarded_points", 0.0)), 2)
            row[f"{cid}_max"] = round(float(c.get("max_points", 0.0)), 2)
            row[f"{cid}_evidence"] = c.get("evidence_quote", "")

        export_rows.append(row)

    df_out = pd.DataFrame(export_rows)
    csv_string = df_out.to_csv(index=False)

    response = StreamingResponse(
        iter([("\ufeff" + csv_string).encode("utf-8")]),
        media_type="text/csv; charset=utf-8"
    )
    response.headers["Content-Disposition"] = f"attachment; filename=rubricgrader_{dataset_id.replace(':', '_')}_export.csv"
    return response


@app.get("/api/report", response_class=HTMLResponse)
def student_report(
    dataset_id: str = Query(..., description="Dataset id"),
    student_id: str = Query(..., description="Student id"),
    weights: Optional[str] = Query(default=None),
    reviewed: bool = Query(default=False),
    download: bool = Query(default=False),
):
    """Render a printable evaluation report for one submission.

    The report is self-contained HTML, includes the student's verbatim answer and all
    rubric evidence, and can be printed to PDF from the browser. The reference answer
    is deliberately never included so a report can be shared with the student.
    """
    payload, df_baseline = _get_baseline(dataset_id)

    raw_weights: Dict[str, float] = {}
    if weights:
        try:
            parsed_weights = json.loads(weights)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="weights must be valid JSON.")
        if not isinstance(parsed_weights, dict):
            raise HTTPException(status_code=400, detail="weights must be a JSON object.")
        raw_weights = parsed_weights
    applied_weights = _sanitize_weights(raw_weights, payload["rubric"])

    df_regraded = regrading_engine.regrade_batch(df_baseline, applied_weights)
    matches = df_regraded[df_regraded["student_id"].astype(str) == str(student_id)]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' is not part of this cohort.")
    record = matches.iloc[0]
    meta = next((s for s in payload["students"] if s["student_id"] == str(student_id)), {})

    evaluations = record.get("regraded_evaluations")
    if evaluations is None:
        evaluations = []
    evaluations = list(evaluations)
    eval_map = {str(c.get("criterion_id")): c for c in evaluations}
    descriptions = {str(c["criterion_id"]): str(c.get("description", "")) for c in payload["rubric"]}

    new_score = float(record["regraded_score"])
    max_score = float(record["regraded_max"])
    human = None
    if "human_score" in record.index and pd.notnull(record["human_score"]):
        human = float(record["human_score"])
    semantic_sim = float(record["semantic_similarity"])
    semantic_pct = float(record["semantic_score_pct"]) if "semantic_score_pct" in record.index else round(semantic_sim * 100, 1)
    confidence = _compute_confidence(evaluations, semantic_sim, human, new_score)
    gap = round(abs(new_score - human), 2) if human is not None else None
    needs_review = confidence["label"] == "Low" or (gap is not None and gap >= 1.5)

    status_labels = {"FULL": "Full credit", "PARTIAL": "Partial credit", "NONE": "Not evidenced"}
    rows_html = []
    for criterion in payload["rubric"]:
        cid = str(criterion["criterion_id"])
        evaluation = eval_map.get(cid, {})
        status = str(evaluation.get("status", "NONE")).upper()
        awarded = float(evaluation.get("awarded_points", 0.0))
        criterion_max = float(evaluation.get("max_points", criterion.get("max_points", 0.0)))
        quote = str(evaluation.get("evidence_quote", "") or "")
        if quote:
            evidence_html = f"&ldquo;{html_lib.escape(quote)}&rdquo;"
            if not bool(evaluation.get("is_quote_verified", False)):
                evidence_html += ' <span class="flag">unverified</span>'
        else:
            evidence_html = '<span class="muted">No verbatim evidence — criterion not addressed.</span>'
        description = descriptions.get(cid) or str(evaluation.get("description", ""))
        rows_html.append(
            "<tr>"
            f'<td><span class="cid">{html_lib.escape(cid)}</span> {html_lib.escape(description)}</td>'
            f'<td><span class="pill {status.lower()}">{html_lib.escape(status_labels.get(status, status))}</span></td>'
            f'<td class="num">{awarded:.2f} <span class="muted">/ {criterion_max:.2f}</span></td>'
            f'<td class="evidence">{evidence_html}</td>'
            "</tr>"
        )

    answer = str(meta.get("student_answer") or record.get("student_answer") or "")
    feedback = str(meta.get("feedback") or "No feedback was generated for this submission.")
    subject = str(payload.get("subject", "Assessment"))
    dataset_label = PRESET_DATASETS.get(dataset_id, {}).get("name") or dataset_id.replace("custom:", "Custom · ")
    human_display = f"{human:.2f}" if human is not None else "N/A"
    gap_display = f"{gap:.2f}" if gap is not None else "—"
    reasons = " · ".join(confidence.get("reasons", []))
    if reviewed:
        review_state = "Teacher approved"
    elif needs_review:
        review_state = "Pending human review"
    else:
        review_state = "No review required"

    query = {
        "dataset_id": dataset_id,
        "student_id": student_id,
        "weights": json.dumps(applied_weights),
        "reviewed": "1" if reviewed else "0",
    }
    download_href = "/api/report?" + urlencode({**query, "download": "1"})

    page_css = """
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 32px 20px; background: #f3ede1; color: #1c1a17;
           font-family: "Segoe UI", system-ui, -apple-system, sans-serif; font-size: 14px; line-height: 1.55; }
    .sheet { max-width: 900px; margin: 0 auto; background: #fffdf8; border: 1px solid #e3dacb;
             border-radius: 14px; box-shadow: 0 18px 50px rgba(60, 45, 25, 0.10); overflow: hidden; }
    .toolbar { max-width: 900px; margin: 0 auto 14px; display: flex; gap: 8px; justify-content: flex-end; }
    .btn { display: inline-block; padding: 9px 14px; border-radius: 8px; border: 1px solid #d8cdbb;
           background: #fffdf8; color: #3a342c; font-size: 12px; font-weight: 600; text-decoration: none; cursor: pointer; }
    .btn.primary { background: #7a2230; border-color: #7a2230; color: #fdf8ef; }
    .head { padding: 30px 34px 24px; border-bottom: 1px solid #ece3d4; }
    .brand { display: flex; align-items: baseline; gap: 10px; }
    .mark { width: 34px; height: 34px; border-radius: 8px; background: #7a2230; color: #f8efe0;
            display: inline-flex; align-items: center; justify-content: center; font-family: Georgia, serif; font-size: 15px; }
    .brand h1 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
    .kicker { font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: #8b8172; }
    .head h2 { margin: 18px 0 4px; font-family: Georgia, "Times New Roman", serif; font-size: 25px; font-weight: 600; }
    .head p { margin: 0; color: #6d6558; font-size: 13px; }
    .head .question { margin-top: 14px; padding-top: 14px; border-top: 1px solid #ece3d4; color: #3a342c;
                      font-family: Georgia, "Times New Roman", serif; font-size: 17px; line-height: 1.45; max-width: 62ch; }
    .meta { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-top: 1px solid #ece3d4; }
    .meta div { padding: 16px 20px; border-right: 1px solid #ece3d4; }
    .meta div:last-child { border-right: 0; }
    .label { font-size: 9.5px; letter-spacing: 0.13em; text-transform: uppercase; color: #8b8172; }
    .value { margin-top: 4px; font-family: "Consolas", "SFMono-Regular", monospace; font-size: 19px; min-height: 24px; }
    .value small { font-size: 11px; color: #9a9082; }
    .sub { margin-top: 3px; font-family: "Consolas", monospace; font-size: 10.5px; color: #9a9082; }
    .body { padding: 26px 34px 30px; }
    h3 { margin: 0 0 8px; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #8b8172; font-weight: 700; }
    .answer { margin: 0 0 26px; padding: 16px 18px; border: 1px solid #e6ddce; border-left: 3px solid #b08a3e;
              border-radius: 8px; background: #faf6ee; white-space: pre-wrap; font-size: 14.5px; line-height: 1.75; }
    .blank { color: #988f81; font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 0 0 26px; }
    th { text-align: left; font-size: 9.5px; letter-spacing: 0.1em; text-transform: uppercase; color: #8b8172;
         border-bottom: 1px solid #ddd3c3; padding: 0 8px 7px; font-weight: 600; }
    td { padding: 12px 8px; border-bottom: 1px solid #ece4d7; vertical-align: top; font-size: 12.5px; }
    td.num { font-family: "Consolas", monospace; white-space: nowrap; }
    td.evidence { color: #5d5548; font-size: 11.5px; line-height: 1.5; width: 34%; }
    .cid { display: inline-block; background: #24211c; color: #f4ecdd; border-radius: 3px; padding: 1px 5px;
           font-family: "Consolas", monospace; font-size: 10px; margin-right: 4px; }
    .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 600; white-space: nowrap; }
    .pill.full { background: #e4efe4; color: #2f6042; border: 1px solid #c6dcc7; }
    .pill.partial { background: #f6ecd4; color: #7d5a17; border: 1px solid #ead9b0; }
    .pill.none { background: #f6e3e2; color: #8a2c2c; border: 1px solid #e7c6c4; }
    .muted { color: #9a9082; }
    .flag { color: #a1472d; font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; }
    .feedback { margin: 0 0 24px; padding: 15px 17px; border: 1px solid #e6ddce; border-radius: 8px; background: #faf7f0; white-space: pre-wrap; }
    .confidence { display: flex; flex-wrap: wrap; gap: 10px 22px; padding: 14px 16px; border-radius: 8px;
                  background: #f7f2e7; border: 1px solid #ece2d0; font-size: 12px; color: #5d5548; }
    .confidence strong { color: #1c1a17; }
    .foot { padding: 16px 34px 20px; border-top: 1px solid #ece3d4; color: #8b8172; font-size: 10.5px;
            display: flex; flex-wrap: wrap; gap: 6px 18px; justify-content: space-between; }
    @media (max-width: 720px) { body { padding: 14px 8px; } .head, .body, .foot { padding-left: 18px; padding-right: 18px; }
      .meta { grid-template-columns: repeat(2, 1fr); } .meta div { border-bottom: 1px solid #ece3d4; }
      td.evidence { width: auto; } table, thead, tbody, th, td, tr { display: block; } thead { display: none; }
      tr { border-bottom: 1px solid #e4dacb; padding: 8px 0; } td { border: 0; padding: 4px 0; } }
    @page { size: A4; margin: 14mm; }
    @media print { body { background: #fff; padding: 0; } .toolbar { display: none; }
      .sheet { border: 0; box-shadow: none; border-radius: 0; max-width: none; } }
    """

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evaluation report · {html_lib.escape(str(student_id))}</title>
<style>{page_css}</style>
</head>
<body>
  <div class="toolbar">
    <a class="btn" href="{download_href}">Download HTML</a>
    <button class="btn primary" type="button" onclick="window.print()">Print / Save as PDF</button>
  </div>
  <main class="sheet">
    <header class="head">
      <div class="brand"><span class="mark">RG</span>
        <div><h1>RubricGrader</h1><div class="kicker">Explainable grading studio · evaluation report</div></div>
      </div>
      <h2>{html_lib.escape(str(student_id))}</h2>
      <p>{html_lib.escape(dataset_label)} · {html_lib.escape(subject)}</p>
      <p class="question">{html_lib.escape(str(payload.get('question', '')))}</p>
    </header>
    <section class="meta">
      <div><div class="label">AI mark</div><div class="value">{new_score:.2f} <small>/ {max_score:.2f}</small></div></div>
      <div><div class="label">Human mark</div><div class="value">{human_display}</div><div class="sub">gap {gap_display}</div></div>
      <div><div class="label">Semantic match</div><div class="value">{semantic_pct:.1f}%</div></div>
      <div><div class="label">Review</div><div class="value" style="font-size:13px">{html_lib.escape(review_state)}</div></div>
    </section>
    <div class="body">
      <h3>What the student wrote</h3>
      <div class="answer">{html_lib.escape(answer) if answer.strip() else '<span class="blank">(blank response)</span>'}</div>

      <h3>Rubric breakdown</h3>
      <table>
        <thead><tr><th>Criterion</th><th>Decision</th><th>Marks</th><th>Verbatim evidence</th></tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>

      <h3>Student feedback</h3>
      <div class="feedback">{html_lib.escape(feedback)}</div>

      <div class="confidence">
        <span><strong>Confidence {confidence['score']}/100</strong> · {html_lib.escape(confidence['label'])}</span>
        <span>{html_lib.escape(reasons)}</span>
      </div>
    </div>
    <footer class="foot">
      <span>Generated {time.strftime('%d %b %Y · %H:%M')} · {html_lib.escape(str(payload['metrics'].get('semantic_engine', 'local')))}</span>
      <span>AI-assisted draft for teacher review. The reference answer is intentionally omitted.</span>
    </footer>
  </main>
</body>
</html>"""

    headers = {}
    if download:
        safe_id = "".join(ch for ch in str(student_id) if ch.isalnum() or ch in "-_") or "student"
        headers["Content-Disposition"] = f'attachment; filename="rubricgrader_report_{safe_id}.html"'
    return HTMLResponse(content=document, headers=headers)


# Serve frontend index
web_dir = os.path.join(CURRENT_DIR, "web")
os.makedirs(web_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=web_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>RubricGrader AI Web Studio initializing...</h1>"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_api:app", host="0.0.0.0", port=8000, reload=True)
