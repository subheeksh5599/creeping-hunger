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
        "headline": result and result["headline"], "blocked": bool(result and result["blocked"]),
        "total_cost_usd": done["total_cost_usd"] if done else None,
        "seconds": done["seconds"] if done else None,
        "billed_usd": done.get("billed_usd") if done else None,
        "fallback_used": bool(result and (result.get("judge") or {}).get("fallback_used")),
        "forced_fallback": forced_fallback,
        "error": error and error["message"],
    }
    (DIR / f"{review_id}.json").write_text(json.dumps({"summary": summary, "events": events}, default=str))


def list_summaries() -> list[dict]:
    if not DIR.exists():
        return []
    rows = [json.loads(p.read_text())["summary"] for p in DIR.glob("*.json")]
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def get(review_id: str) -> dict | None:
    p = DIR / f"{review_id}.json"
    return json.loads(p.read_text()) if p.is_file() and p.parent == DIR else None


def latest_for(url: str) -> dict | None:
    """The newest finished, unforced review of this URL from the last 24 hours."""
    cutoff = time.time() - CACHE_SECONDS
    for row in list_summaries():
        if row["created_at"] < cutoff:
            return None
        if row["url"] == url and row["score"] and not row["error"] and not row.get("forced_fallback"):
            return get(row["id"])
    return None
