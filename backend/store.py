"""Reviews persisted as one JSON file each under data/reviews/."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "reviews"
SEED = Path(__file__).resolve().parent.parent / "samples" / "reviews"


def seed() -> None:
    """Copies the committed demo reviews in, so a fresh deploy with no disk still has history."""
    DIR.mkdir(parents=True, exist_ok=True)
    for p in SEED.glob("*.json"):
        if not (DIR / p.name).exists():
            shutil.copy(p, DIR / p.name)


seed()


CACHE_SECONDS = 24 * 3600


def save(review_id: str, install_id: str, url: str, events: list[dict], forced_fallback: bool = False) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    result = next((e for e in events if e["type"] == "result"), None)
    done = next((e for e in events if e["type"] == "done"), None)
    error = next((e for e in events if e["type"] == "error"), None)
    summary = {
        "id": review_id, "install_id": install_id, "url": url, "created_at": time.time(),
        "brand": result and result["brand"], "product": result and result["product"],
        "score": result and result["score"], "label": result and result["label"],
        "score_by": result and result.get("score_by"),
        "headline": result and result["headline"], "blocked": bool(result and result["blocked"]),
        "total_cost_usd": done["total_cost_usd"] if done else None,
        "seconds": done["seconds"] if done else None,
        "billed_usd": done.get("billed_usd") if done else None,
        "fallback_used": bool(result and (result.get("judge") or {}).get("fallback_used")),
        "forced_fallback": forced_fallback,
        "error": error and error["message"],
    }
    tmp = DIR / f"{review_id}.json.tmp"
    tmp.write_text(json.dumps({"summary": summary, "events": events}, default=str))
    tmp.replace(DIR / f"{review_id}.json")


def _summary(p: Path) -> dict | None:
    """A half-written or hand-edited file is skipped, so one bad file can't break the dashboard or every review."""
    try:
        row = json.loads(p.read_text())["summary"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return row if isinstance(row, dict) and isinstance(row.get("created_at"), (int, float)) else None


def list_summaries() -> list[dict]:
    if not DIR.exists():
        return []
    rows = [r for r in map(_summary, DIR.glob("*.json")) if r]
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def get(review_id: str) -> dict | None:
    p = DIR / f"{review_id}.json"
    if not (p.is_file() and p.parent == DIR):
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def latest_for(url: str) -> dict | None:
    """The newest finished, unforced review of this URL from the last 24 hours, made by the current pipeline
    (one that records who set the score), so a seeded pre-formula review is never replayed as today's."""
    cutoff = time.time() - CACHE_SECONDS
    for row in list_summaries():
        if row["created_at"] < cutoff:
            return None
        if (row.get("url") == url and row.get("score") and row.get("score_by") and not row.get("error")
                and not row.get("forced_fallback")):
            return get(row["id"])
    return None
