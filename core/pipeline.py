"""EXAMPLE pipeline: review a document and return structured, source-backed findings.

This is a placeholder for the walking skeleton. Once the challenge is chosen, change
SYSTEM_PROMPT, the Finding/AnalysisResult fields and _mock_analysis -- keep the shape:
  input -> AI step with evidence -> human decision -> audit trail.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from core.audit import log_event
from core.llm import complete_json, model, provider


class Finding(BaseModel):
    issue: str = Field(description="What looks wrong or noteworthy, one sentence")
    severity: Literal["low", "medium", "high"]
    evidence: str = Field(description="Exact quote from the document that supports the issue")


class AnalysisResult(BaseModel):
    case_id: str
    summary: str
    risk_level: Literal["low", "medium", "high"]
    findings: list[Finding]
    missing_information: list[str]
    recommended_action: str
    needs_human_review: bool
    model: str


SYSTEM_PROMPT = """You are a careful banking compliance analyst assistant.
Review the document and return ONLY a JSON object with these keys:
  "summary": 2-3 sentences,
  "risk_level": "low" | "medium" | "high",
  "findings": [{"issue": str, "severity": "low"|"medium"|"high", "evidence": exact quote from the document}],
  "missing_information": [str],
  "recommended_action": one sentence,
  "needs_human_review": true | false
Rules: every finding MUST quote evidence verbatim from the document. Never invent facts.
If unsure, say so and set needs_human_review to true. The final decision is always made by a human."""

RED_FLAG_KEYWORDS = {  # keyword -> (issue, severity); only used in mock mode
    "sanction": ("Possible sanctions exposure mentioned", "high"),
    "offshore": ("Offshore structure in ownership chain", "high"),
    "shell company": ("Possible shell company in ownership chain", "high"),
    "nominee": ("Nominee shareholders or directors", "high"),
    "politically exposed": ("Politically exposed person (PEP) involved", "high"),
    "cash-intensive": ("Cash-intensive business model", "medium"),
    "adverse media": ("Adverse media reported", "high"),
    "not provided": ("Required information not provided", "high"),
    "vacant": ("Key control function vacant", "medium"),
    "warning": ("Past regulatory warning", "medium"),
}


def _mock_analysis(document: str) -> dict:
    """Deterministic fake answer so the UI works without an API key."""
    lower = document.lower()
    findings = []
    for keyword, (issue, severity) in RED_FLAG_KEYWORDS.items():
        idx = lower.find(keyword)
        if idx == -1 or "no " in lower[max(0, idx - 30) : idx]:  # skip negations like "no sanctions hits"
            continue
        start = lower.rfind("\n", 0, idx) + 1
        end = lower.find("\n", idx)
        evidence = document[start : end if end != -1 else len(document)].strip()
        findings.append({"issue": issue, "severity": severity, "evidence": evidence[:240]})
    has_high = any(f["severity"] == "high" for f in findings)
    risk = "high" if has_high and len(findings) >= 2 else "medium" if findings else "low"
    return {
        "summary": f"[MOCK] Reviewed {len(document.split())} words; {len(findings)} potential issue(s) found.",
        "risk_level": risk,
        "findings": findings,
        "missing_information": ["Ultimate beneficial owner documentation"] if "not provided" in lower else [],
        "recommended_action": "Escalate to enhanced due diligence" if findings else "Proceed with standard review",
        "needs_human_review": bool(findings),
    }


def analyze(document: str, source_name: str = "document") -> AnalysisResult:
    case_id = uuid.uuid4().hex[:8]
    raw = complete_json(SYSTEM_PROMPT, f"Document ({source_name}):\n\n{document}", mock=_mock_analysis)
    result = AnalysisResult(case_id=case_id, model=f"{provider()}:{model()}", **raw)
    log_event("ai_analysis", case_id, {"source": source_name, "result": result.model_dump()})
    return result


def record_decision(case_id: str, decision: str, reviewer: str, comment: str = "") -> dict:
    return log_event(
        "human_decision", case_id, {"decision": decision, "comment": comment}, actor=reviewer
    )
