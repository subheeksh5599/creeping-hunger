"""Creeping Hunger backend: FastAPI app serving the review stream, the guardrail service and the web UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import guard
import store
from otari import Otari, OtariError
from pipeline import Review

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Creeping Hunger", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ReviewIn(BaseModel):
    url: str
    page_text: str | None = None
    page_html: str | None = None
    install_id: str = "anon"
    force_fallback: bool = False


def sse(gen):
    async def stream():
        async for event in gen:
            yield f"data: {json.dumps(event, default=str)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/review")
async def review(body: ReviewIn):
    page_text = body.page_text[:60000] if body.page_text else None
    page_html = body.page_html[:400000] if body.page_html else None
    return sse(Review(body.url, page_text, page_html, body.install_id, body.force_fallback).run())


@app.get("/api/review")
async def review_get(url: str, install_id: str = "anon", force_fallback: bool = False):
    return sse(Review(url, None, None, install_id, force_fallback).run())


@app.get("/api/reviews")
async def reviews():
    return store.list_summaries()


@app.get("/api/reviews/{review_id}")
async def review_detail(review_id: str):
    r = store.get(review_id)
    return r if r else JSONResponse({"detail": "not found"}, status_code=404)


@app.get("/api/budget/{install_id}")
async def budget(install_id: str):
    o = Otari()
    try:
        rows = await o.get(f"/end-users?external_id=ch-install:{install_id}")
        return {"available": True, "end_user": rows[0] if rows else None}
    except OtariError as e:
        return {"available": False, "reason": e.detail}
    finally:
        await o.aclose()


# ---- guardrail service (Otari's contract) ------------------------------------
@app.get("/guardrail/profiles")
async def guard_profiles():
    return [{"name": "prompt-injection", "guardrail_name": "creeping_hunger_injection"}]


@app.post("/guardrail/validate")
async def guard_validate(req: Request):
    body = await req.json()
    if os.getenv("GUARDRAIL_TOKEN") and req.headers.get("authorization") != f"Bearer {os.environ['GUARDRAIL_TOKEN']}":
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    res = await guard.validate(body.get("input_text", ""))
    print(f"[guardrail] called by Otari: valid={res['valid']} score={res['score']}", flush=True)
    return {"profile": body.get("profile", "prompt-injection"),
            "result": {"valid": res["valid"], "explanation": res["explanation"], "score": res["score"]}}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "otari_key_present": bool(os.getenv("OTARI_API_KEY")),
            "public_base_url": os.getenv("PUBLIC_BASE_URL") or None,
            "mcp_public_url": os.getenv("MCP_PUBLIC_URL") or None}


app.mount("/hostile", StaticFiles(directory=ROOT / "hostile", html=True), name="hostile")
app.mount("/ui", StaticFiles(directory=ROOT / "extension"), name="ui")


DIST = ROOT / "dashboard" / "dist"


@app.get("/try")
async def try_page():
    return FileResponse(ROOT / "web" / "index.html")


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
