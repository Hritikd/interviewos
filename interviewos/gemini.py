from __future__ import annotations

import json
from typing import Any

import httpx

from interviewos.models import JobHit

_MODEL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"


def plan_search(api_key: str, background: str) -> dict[str, Any] | None:
    """Ask Gemini which job titles to search after reading the candidate."""
    if not api_key.strip() or not background.strip():
        return None
    prompt = (
        "Read the candidate and decide which live job titles to search. "
        'Return JSON only: {"titles": [string, string, string, string], "focus": string}. '
        "titles are exact phrases that appear on postings, four of them. "
        "Do not use the bare title Product Manager. "
        "focus is one sentence about the work they have actually done. "
        "Do not invent employers or metrics.\n\n"
        f"Candidate:\n{background[:2000]}"
    )
    return _ask_json(api_key, prompt)


def select_jobs(api_key: str, background: str, jobs: list[JobHit]) -> list[int] | None:
    """Return indexes Gemini keeps. None means the call failed and the caller should use its own ranking."""
    if not api_key.strip() or not jobs or not background.strip():
        return None
    rows = [
        {
            "index": index,
            "title": job.title,
            "company": job.company_name,
            "posting": (job.description_excerpt or "")[:400],
        }
        for index, job in enumerate(jobs[:8])
    ]
    prompt = (
        "Keep a job only when the posting matches the work in the background. "
        "Reject credit-risk, payments-operations, branch banking, and title-only matches. "
        'Return JSON only: {"keep": [indexes]}. Use no more than 2.\n\n'
        f"Candidate background:\n{background[:1800]}\n\nJobs:\n{json.dumps(rows)}"
    )
    parsed = _ask_json(api_key, prompt)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("keep"), list):
        return None
    return [item for item in parsed["keep"] if isinstance(item, int) and 0 <= item < len(jobs)]


def _ask_json(api_key: str, prompt: str) -> dict[str, Any] | None:
    try:
        response = httpx.post(
            _MODEL,
            params={"key": api_key.strip()},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
            },
            timeout=60,
        )
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError):
        return None
