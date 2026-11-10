"""Turn uploaded files into plain text. Text-based PDFs only: skip OCR during a hackathon."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT / "data" / "scenarios"


def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        import fitz  # PyMuPDF

        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    return data.decode("utf-8", errors="replace")


def list_scenarios() -> dict[str, str]:
    """Demo scenarios: {display name: text}. Keep 3: clean, red flags, edge case."""
    return {
        p.stem.replace("_", " ").title(): p.read_text(encoding="utf-8")
        for p in sorted(SCENARIO_DIR.glob("*.txt"))
    }
