"""Run a review from the terminal and save the event stream: python scripts/review_cli.py URL [out.json] [--fallback]"""
import json
import sys

import os

import httpx

url = sys.argv[1]
out = next((a for a in sys.argv[2:] if a.endswith(".json")), None)
backend = os.getenv("CH_BACKEND", "http://127.0.0.1:8787").rstrip("/")  # e.g. https://creeping-hunger.onrender.com
events = []
with httpx.stream("POST", f"{backend}/api/review", timeout=600,
                  json={"url": url, "install_id": os.getenv("CH_INSTALL_ID", "cli-test"), "force_fallback": "--fallback" in sys.argv}) as r:
    for line in r.iter_lines():
        if not line.startswith("data: "):
            continue
        e = json.loads(line[6:])
        events.append(e)
        if e["type"] == "token":
            print(e["text"], end="", flush=True)
            continue
        brief = {k: e.get(k) for k in ("id", "status", "title", "model", "detail", "cost_usd", "message", "code") if e.get(k) is not None}
        if e["type"] == "step" and e.get("otari"):
            o = e["otari"]
            brief["otari"] = {k: o.get(k) for k in ("otari-model", "otari-fallback", "otari-attempt-count", "otari-guardrails") if o.get(k)}
        print(f"\n[{e['type']}] {json.dumps(brief)}" if e["type"] != "result" else f"\n[result] score={e['score']} {e['label']} | {e['headline']}")
        if e["type"] in ("done", "error"):
            print(json.dumps(e)[:1500])
if out:
    json.dump(events, open(out, "w"), indent=1)
