"""Reviews persisted as one JSON file each under data/reviews/."""
from __future__ import annotations

import json
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "reviews"


def save(review_id: str, install_id: str, url: str, events: list[dict]) -> None:
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
