"""FastAPI backend. Needed if the frontend is Next.js/React; the Streamlit app calls core/ directly.

Run:  uvicorn api.main:app --reload      (docs at http://127.0.0.1:8000/docs)
"""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.audit import read_events
from core.documents import extract_text, list_scenarios
from core.llm import model, provider
from core.pipeline import AnalysisResult, analyze, record_decision

app = FastAPI(title="Build Days API", version="0.1.0")
app.add_middleware(  # open CORS: fine for a hackathon demo, never for production
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class AnalyzeRequest(BaseModel):
    text: str
    source_name: str = "document"


class DecisionRequest(BaseModel):
    case_id: str
    decision: str  # approve | reject | escalate
    reviewer: str
    comment: str = ""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": provider(), "model": model()}


@app.get("/scenarios")
def scenarios() -> dict[str, str]:
    return list_scenarios()


@app.post("/analyze", response_model=AnalysisResult)
def analyze_text(req: AnalyzeRequest) -> AnalysisResult:
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    return analyze(req.text, req.source_name)


@app.post("/analyze/file", response_model=AnalysisResult)
async def analyze_file(file: UploadFile = File(...)) -> AnalysisResult:
    text = extract_text(file.filename or "upload.txt", await file.read())
    return analyze(text, file.filename or "upload")


@app.post("/decision")
def decision(req: DecisionRequest) -> dict:
    return record_decision(req.case_id, req.decision, req.reviewer, req.comment)


@app.get("/audit")
def audit(case_id: str | None = None) -> list[dict]:
    return read_events(case_id)
