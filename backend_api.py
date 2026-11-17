"""
backend_api.py
--------------
High-performance FastAPI backend bridging the RubricGrader AI core engine
with the Cyber-Studio React + Three.js WebGL frontend.
"""

import os
import sys
import time
import io
from typing import Dict, Any, List, Optional
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure workspace root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.data_loader import DataLoader
from core.similarity_engine import SemanticSimilarityEngine
from core.rubric_evaluator import RubricEvaluator
from core.feedback_engine import FeedbackEngine
from core.regrading_engine import RegradingEngine
from core.cache_manager import CacheManager
from core.metrics import flag_borderline_answers, calculate_qwk

app = FastAPI(
    title="RubricGrader AI - Cyber-Studio API",
    description="Explainable, Sub-10ms Rubric Evaluation Engine with Three.js Visualizer",
    version="2.0.0"
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
sim_engine = SemanticSimilarityEngine(use_fallback=True)
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
        "file": os.path.join("data", "sample_biology.csv"),
        "subject_filter": "Biology"
    },
    "cs": {
        "id": "cs",
        "name": "Recursion vs Iteration (Computer Science)",
        "file": os.path.join("data", "sample_cs.csv"),
        "subject_filter": "Computer Science"
    },
    "history": {
        "id": "history",
        "name": "Industrial Revolution (History)",
        "file": os.path.join("data", "sample_history.csv"),
        "subject_filter": "History"
    },
    "ml": {
        "id": "ml",
        "name": "Machine Learning (Supervised vs Unsupervised)",
        "file": os.path.join("data", "sample_custom_ml.csv"),
        "subject_filter": "Machine Learning"
    }
}

# In-memory storage for active uploaded custom dataset
custom_uploaded_df: Optional[pd.DataFrame] = None


def process_dataset(df_raw: pd.DataFrame, subject_name: str) -> Dict[str, Any]:
    """Execute complete scoring and evaluation pipeline on filtered DataFrame."""
    question, model_answer, parsed_rubric = loader.get_subject_metadata(df_raw)

    # 1. Semantic Similarity
    df_scored = sim_engine.score_dataframe(df_raw)

    # 2. Rubric Evaluation with cached lookups
    eval_results = []
    rubric_scores = []
    rubric_pcts = []
    for _, row in df_scored.iterrows():
        sa = str(row["student_answer"])
        rj = str(row.get("rubric_json", ""))
        cached = cache_mgr.get_cached_evaluation(sa, rj)
        if cached:
            res = cached
        else:
            res = evaluator.evaluate_answer(
                question, model_answer, parsed_rubric, sa, use_heuristic_fallback=True
            )
            cache_mgr.save_evaluation(sa, rj, res)
        eval_results.append(res)
        rubric_scores.append(res["total_awarded"])
        rubric_pcts.append(res["overall_percentage"])

    df_scored["rubric_results"] = eval_results
    df_scored["rubric_score"] = rubric_scores
    df_scored["rubric_pct"] = rubric_pcts

    # 3. Feedback attachment
    df_scored = feedback_engine.attach_feedback_to_dataframe(df_scored, default_model_answer=model_answer)

    # 4. Borderline review flagging
    df_scored = flag_borderline_answers(df_scored, score_col="rubric_score", human_col="human_score", threshold=1.5)

    # 5. Metrics calculation
    total_submissions = len(df_scored)
    avg_sim = round(float(df_scored["semantic_score_pct"].mean()), 1)
    avg_rubric = round(float(df_scored["rubric_score"].mean()), 2)
    max_pts = sum(c["max_points"] for c in parsed_rubric)

    # QWK
    qwk_info = calculate_qwk(df_scored["rubric_score"], df_scored["human_score"], max_rating=int(max_pts) if max_pts else 5)
    mae_val = qwk_info.get("mean_absolute_error", 0.0)

    # Prepare students payload
    students_payload = []
    for _, r in df_scored.iterrows():
        students_payload.append({
            "student_id": str(r["student_id"]),
            "student_answer": str(r["student_answer"]),
            "human_score": float(r["human_score"]) if pd.notnull(r.get("human_score")) else None,
            "semantic_score_pct": float(r["semantic_score_pct"]),
            "semantic_similarity": float(r["semantic_similarity"]),
            "semantic_band": str(r["semantic_band"]),
            "rubric_score": float(r["rubric_score"]),
            "rubric_pct": float(r["rubric_pct"]),
            "rubric_results": r["rubric_results"].get("criterion_evaluations", []),
            "feedback": str(r.get("student_feedback", "")),
            "leak_free": bool(r.get("feedback_leak_free", True)),
            "is_borderline": bool(r.get("is_borderline", False)),
            "score_discrepancy": float(r.get("score_discrepancy", 0.0))
        })

    return {
        "subject": subject_name,
        "question": question,
        "model_answer": model_answer,
        "rubric": parsed_rubric,
        "students": students_payload,
        "metrics": {
            "total_submissions": total_submissions,
            "avg_semantic_match": avg_sim,
            "avg_rubric_score": avg_rubric,
            "max_possible_score": max_pts,
            "qwk_score": qwk_info["qwk_score"],
            "qwk_interpretation": qwk_info["interpretation"],
            "mae": mae_val,
            "borderline_count": int(df_scored["is_borderline"].sum())
        }
    }


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "engine": "RubricGrader AI Cyber-Studio",
        "cache_entries": len(cache_mgr.cache_data),
        "version": "2.0.0"
    }


@app.get("/api/datasets")
def list_datasets():
    datasets = [
        {"id": k, "name": v["name"], "type": "preset"}
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
    return {"datasets": datasets}


@app.get("/api/assessment")
def get_assessment(dataset_id: str = Query(default="biology")):
    global custom_uploaded_df

    if dataset_id.startswith("custom:"):
        if custom_uploaded_df is None:
            raise HTTPException(status_code=400, detail="No custom dataset has been uploaded.")
        subj = dataset_id.replace("custom:", "", 1)
        filtered = loader.filter_by_subject(custom_uploaded_df, subj)
        return process_dataset(filtered, subj)

    if dataset_id not in PRESET_DATASETS:
        dataset_id = "biology"

    preset = PRESET_DATASETS[dataset_id]
    df_raw = loader.load_csv(preset["file"])
    filtered = loader.filter_by_subject(df_raw, preset["subject_filter"])
    return process_dataset(filtered, preset["subject_filter"])


class RegradeRequest(BaseModel):
    dataset_id: str
    slider_weights: Dict[str, float]


@app.post("/api/regrade")
def regrade_assessment(req: RegradeRequest):
    t_start = time.perf_counter()

    # Get the dataset records
    if req.dataset_id.startswith("custom:"):
        if custom_uploaded_df is None:
            raise HTTPException(status_code=400, detail="No custom dataset has been uploaded.")
        subj = req.dataset_id.replace("custom:", "", 1)
        df_raw = loader.filter_by_subject(custom_uploaded_df, subj)
    else:
        preset_key = req.dataset_id if req.dataset_id in PRESET_DATASETS else "biology"
        preset = PRESET_DATASETS[preset_key]
        df_raw = loader.load_csv(preset["file"])
        df_raw = loader.filter_by_subject(df_raw, preset["subject_filter"])

    # Full evaluation
    data = process_dataset(df_raw, "Active")

    # Reconstruct a DataFrame for RegradingEngine
    records = []
    for s in data["students"]:
        records.append({
            "student_id": s["student_id"],
            "student_answer": s["student_answer"],
            "human_score": s["human_score"],
            "rubric_score": s["rubric_score"],
            "rubric_results": {"criterion_evaluations": s["rubric_results"]}
        })
    df_regrade = pd.DataFrame(records)

    diff_report = regrading_engine.compute_score_diff(df_regrade, req.slider_weights, human_col="human_score")
    diff_df = diff_report["diff_dataframe"]

    diff_rows = []
    for _, r in diff_df.iterrows():
        diff_rows.append({
            "student_id": str(r["student_id"]),
            "old_score": float(r["old_score"]),
            "new_score": float(r["new_score"]),
            "score_delta": float(r["score_delta"]),
            "change_status": str(r["change_status"]),
            "explanation": str(r["explanation"]),
        })

    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    return {
        "diff_rows": diff_rows,
        "old_qwk": diff_report.get("old_qwk"),
        "new_qwk": diff_report.get("new_qwk"),
        "new_max_score": sum(req.slider_weights.values()),
        "new_avg_score": round(float(diff_df["new_score"].mean()), 2),
        "recalculation_latency_ms": latency_ms
    }


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global custom_uploaded_df
    try:
        content = await file.read()
        buffer = io.BytesIO(content)
        df_parsed = loader.load_csv(buffer)
        custom_uploaded_df = df_parsed
        subjects = loader.get_available_subjects(df_parsed)
        return {
            "success": True,
            "filename": file.filename,
            "rows_count": len(df_parsed),
            "subjects": subjects,
            "default_subject": subjects[0] if subjects else "General"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


@app.get("/api/export_csv")
def export_csv(dataset_id: str = Query(default="biology")):
    if dataset_id.startswith("custom:"):
        if custom_uploaded_df is None:
            raise HTTPException(status_code=400, detail="No custom dataset uploaded.")
        subj = dataset_id.replace("custom:", "", 1)
        df_raw = loader.filter_by_subject(custom_uploaded_df, subj)
    else:
        preset_key = dataset_id if dataset_id in PRESET_DATASETS else "biology"
        preset = PRESET_DATASETS[preset_key]
        df_raw = loader.load_csv(preset["file"])
        df_raw = loader.filter_by_subject(df_raw, preset["subject_filter"])

    data = process_dataset(df_raw, "Export")
    export_rows = []
    for s in data["students"]:
        export_rows.append({
            "student_id": s["student_id"],
            "student_answer": s["student_answer"],
            "semantic_score_pct": s["semantic_score_pct"],
            "rubric_score": s["rubric_score"],
            "human_score": s["human_score"],
            "feedback": s["feedback"],
            "is_borderline": s["is_borderline"]
        })
    df_out = pd.DataFrame(export_rows)
    stream = io.StringIO()
    df_out.to_csv(stream, index=False)
    stream.seek(0)

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=rubricgrader_{dataset_id}_export.csv"
    return response


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
