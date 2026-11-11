"""Whole reviews against a fake Otari gateway: the hostile page, Fitbit-like pages, judge routing, budget errors, MCP modes."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

import otari
import pipeline
from otari import OtariError
from pipeline import BROKEN_MODEL, Review, same_site

ROOT = Path(__file__).resolve().parent.parent
HOSTILE_HTML = (ROOT / "hostile" / "index.html").read_text()
HOSTILE_POLICY_HTML = (ROOT / "hostile" / "privacy.html").read_text()
HOSTILE_MD = pipeline.html_to_text(HOSTILE_HTML).replace("Privacy Policy", "[Privacy Policy](privacy.html)")
POLICY_MD = pipeline.html_to_text(HOSTILE_POLICY_HTML)
CLEAN_PAGE = "Acme Band 3. A fitness band. [Privacy](https://acme.test/privacy) " + "Great battery. " * 50
CLEAN_POLICY = ("Acme collects personal information such as heart rate and location. We may share it with partners. " * 20
                + "It may take up to 90 days to delete all of your information.")
EXTRACTION = {"data_collected": ["heart rate"], "sensitive_data": ["health", "location"], "sells_data": "no",
              "retention": "up to 90 days", "red_flags": [{"flag": "Slow delete", "quote": "It may take up to 90 days to delete all of your information"}]}
VERDICT = "SCORE: 2\nLABEL: A little creepy\nHEADLINE: Fine\nWARNING: no\n---\nWords.\n\nTips to protect yourself:\n- one\n- two"


def chat_reply(text, cost=0.001):
    return {"choices": [{"message": {"content": text}}], "usage": {"cost_usd": cost}, "otari_tool_calls": [
        {"type": "mcp", "status": "completed", "server": "creeping-hunger", "name": "hibp_breaches"}]}


class Gateway:
    """Answers like Otari, by path and model, and records every request."""

    def __init__(self, *, pages=None, search=None, judge_fail=(), fatal_at=None, guard_says=0, sandbox_ok=True,
                 mcp_refuse=False, servers=None, extractor_reply=None, fetch_ok=True, web_tools=True):
        self.pages = pages or {}
        self.search_results = search or []
        self.judge_fail = set(judge_fail)
        self.fatal_at, self.guard_says, self.sandbox_ok = fatal_at, guard_says, sandbox_ok
        self.mcp_refuse, self.servers = mcp_refuse, servers if servers is not None else [{"id": "srv-1", "name": "creeping-hunger"}]
        self.extractor_reply = extractor_reply or json.dumps(EXTRACTION)
        self.fetch_ok, self.web_tools = fetch_ok, web_tools
        self.log: list[tuple[str, dict]] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path.removeprefix("/api/v1")
        body = json.loads(req.content) if req.content else {}
        self.log.append((path, body))
        if self.fatal_at and self.fatal_at(path, body):
            return httpx.Response(403, json={"detail": "Budget exceeded", "code": "budget_exceeded"})
        if path == "/tools":
            return httpx.Response(200, json={"data": [{"id": "otari_web_search", "available": self.web_tools},
                                                      {"id": "otari_web_fetch", "available": self.web_tools},
                                                      {"id": "otari_code_execution", "available": True}]})
        if path == "/mcp/servers":
            return httpx.Response(200, json={"servers": self.servers})
        if path.startswith("/end-users"):
            spend = 0.04 * sum(1 for p, _ in self.log if p == "/chat/completions") / 6
            return httpx.Response(200, json=[{"spend": round(spend, 4), "next_budget_reset_at": "2026-11-12T00:00:00Z"}])
        if path == "/fetch":
            content = self.pages.get(body["url"])
            if not self.fetch_ok or content is None:
                return httpx.Response(404, json={"detail": "fetch failed"})
            return httpx.Response(200, json={"content": content})
        if path == "/search":
            return httpx.Response(200, json={"results": [{"url": u} for u in self.search_results]})
        if path == "/code/execute":
            if not self.sandbox_ok:
                return httpx.Response(504, json={"detail": "sandbox timeout"})
            out = pipeline.run_compute_locally(body["code"])
            return httpx.Response(200, json={"stdout": json.dumps(out) + "\n"}, headers={"otari-request-id": "code-1"})
        if path == "/chat/completions":
            return self.chat(body)
        return httpx.Response(404, json={"detail": f"unknown {path}"})

    def chat(self, body):
        model = body["model"]
        headers = {"otari-model": model, "otari-provider": "fake"}
        if body.get("stream"):
            if model in self.judge_fail or model == BROKEN_MODEL:
                return httpx.Response(424, json={"detail": "model unavailable"})
            served = "meta/llama-3.3-70b-instruct" if model == "creeping-hunger-judge" else model
            chunks = [{"choices": [{"delta": {"content": VERDICT[i:i + 20]}}]} for i in range(0, len(VERDICT), 20)]
            chunks.append({"choices": [], "usage": {"cost_usd": 0.002}})
            sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, content=sse.encode(), headers={**headers, "otari-model": served})
        system = body["messages"][0]["content"]
        if model == pipeline.guard.GUARD_MODEL:
            return httpx.Response(200, json=chat_reply(json.dumps({"violation": self.guard_says, "confidence": 0.9, "evidence": "planted"})), headers=headers)
        if "Identify the consumer product" in system:
            return httpx.Response(200, json=chat_reply('{"brand": "SnoopCam", "product": "Doorbell Pro", "brand_domain": "snoopcam.com"}'), headers=headers)
        if "extract data practices" in system:
            return httpx.Response(200, json=chat_reply(self.extractor_reply), headers=headers)
        if "Return the user's JSON fixed" in system:
            return httpx.Response(200, json=chat_reply("still broken"), headers=headers)
        if "research desk" in system:
            if self.mcp_refuse and ("mcp_server_ids" in body or "mcp_servers" in body):
                return httpx.Response(403, json={"detail": "MCP servers are not allowed for this workspace."})
            return httpx.Response(200, json=chat_reply('{"breaches": [], "tosdr_grade": "C", "sources": []}'), headers=headers)
        return httpx.Response(400, json={"detail": "unexpected chat"})


@pytest.fixture(autouse=True)
def offline_tools(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(otari.asyncio, "sleep", instant)
    monkeypatch.setattr(pipeline.mcp_tools, "hibp_breaches_impl", lambda d: {"domain": d, "breaches": []})
    monkeypatch.setattr(pipeline.mcp_tools, "tosdr_impl", lambda d: {"found": True, "grade": "C", "service": "S", "url": "https://tosdr.org/en/service/9"})
    monkeypatch.setattr(pipeline.mcp_tools, "pni_archive_impl", lambda b, p="": {"found": False})


def review_with(gateway, url, page_text=None, page_html=None, force=False, local_pages=None, policy=""):
    pipeline.JUDGE_POLICY = policy
    r = Review(url, page_text, page_html, "unit", force_fallback=force, fresh=True)
    r.o._c = httpx.AsyncClient(transport=httpx.MockTransport(gateway))
    pages = local_pages or {}

    def local(req):
        if str(req.url).startswith("https://archive.org/wayback/available"):
            return httpx.Response(200, json={"archived_snapshots": {}})
        html = pages.get(str(req.url))
        return httpx.Response(200, text=html, headers={"content-type": "text/html"}) if html else httpx.Response(404, text="nope")
    r.local_http = httpx.AsyncClient(transport=httpx.MockTransport(local), follow_redirects=True)
    return r


def events_of(r):
    async def go():
        return [e async for e in r.run()]
    try:
        return asyncio.run(go())
    finally:
        pipeline.JUDGE_POLICY = ""


def step(events, sid, status=None):
    rows = [e for e in events if e.get("type") == "step" and e["id"] == sid and (status is None or e["status"] == status)]
    return rows[-1] if rows else None


RENDER_HOSTILE = "https://creeping-hunger.onrender.com/hostile/"


@pytest.mark.parametrize("search", [[], ["https://evil-app.onrender.com/privacy"], ["https://onrender.com/privacy", "https://render.com/privacy"]])
@pytest.mark.parametrize("guard_says", [0, 1])
@pytest.mark.parametrize("force", [False, True])
def test_hostile_page_read_through_otari_fetch_finds_its_own_policy_and_is_blocked(search, guard_says, force):
    gw = Gateway(pages={RENDER_HOSTILE: HOSTILE_MD, RENDER_HOSTILE + "privacy.html": POLICY_MD}, search=search, guard_says=guard_says)
    events = events_of(review_with(gw, RENDER_HOSTILE, force=force, policy="creeping-hunger-judge"))
    assert step(events, "policy", "done")["url"] == RENDER_HOSTILE + "privacy.html"
    assert step(events, "guard")["status"] == "error"
    assert step(events, "extract")["status"] == "skipped"
    result = next(e for e in events if e["type"] == "result")
    assert (result["score"], result["blocked"], result["score_by"]) == (5, True, "code")
    assert result["judge"]["fallback_used"] is force
    assert not any(p == "/chat/completions" and "extract data practices" in b["messages"][0]["content"] for p, b in gw.log)
    assert events[-1]["type"] == "done"


@pytest.mark.parametrize("base", ["http://127.0.0.1:8787/hostile/", "http://localhost:8787/hostile/"])
def test_hostile_page_from_the_extension_dom_uses_the_html_link(base):
    gw = Gateway()
    r = review_with(gw, base, page_text=pipeline.html_to_text(HOSTILE_HTML), page_html=HOSTILE_HTML,
                    local_pages={base + "privacy.html": HOSTILE_POLICY_HTML})
    events = events_of(r)
    assert step(events, "policy", "done")["url"] == base + "privacy.html"
    assert next(e for e in events if e["type"] == "result")["score"] == 5
    assert not any(p == "/fetch" for p, _ in gw.log)


@pytest.mark.parametrize("url,domain,pinned,ok", [
    ("https://creeping-hunger.onrender.com/hostile/privacy.html", "creeping-hunger.onrender.com", True, True),
    ("https://evil.onrender.com/privacy", "creeping-hunger.onrender.com", True, False),
    ("https://www.fitbit.com/global/us/legal/privacy-policy", "fitbit.com", False, True),
    ("https://help.fitbit.com/privacy", "fitbit.com", False, True),
    ("https://fitbit.evil.com/privacy", "fitbit.com", False, False),
    ("https://me.github.io/privacy", "you.github.io", True, False),
    ("https://you.github.io/privacy", "you.github.io", True, True),
])
def test_same_site(url, domain, pinned, ok):
    assert same_site(url, domain, pinned) is ok


ACME = "https://acme.test/band-3"


def acme_gateway(**kw):
    return Gateway(pages={ACME: CLEAN_PAGE, "https://acme.test/privacy": CLEAN_POLICY}, **kw)


@pytest.mark.parametrize("policy,force,fail,expect_models,fallback", [
    ("", False, (), ["meta/llama-3.3-70b-instruct"], False),
    ("", True, (), [BROKEN_MODEL, "mistralai/mistral-small-3.2-24b-instruct-2506"], True),
    ("", False, ("meta/llama-3.3-70b-instruct",), ["meta/llama-3.3-70b-instruct", "mistralai/mistral-small-3.2-24b-instruct-2506"], True),
    ("creeping-hunger-judge", False, (), ["creeping-hunger-judge"], False),
    ("creeping-hunger-judge", True, (), [BROKEN_MODEL, "creeping-hunger-judge"], True),
])
def test_judge_routes(policy, force, fail, expect_models, fallback):
    gw = acme_gateway(judge_fail=fail)
    events = events_of(review_with(gw, ACME, force=force, policy=policy))
    sent = [b["model"] for p, b in gw.log if p == "/chat/completions" and b.get("stream")]
    assert sent == expect_models
    done = step(events, "judge", "done")
    assert done["fallback_used"] is fallback
    assert [f["status"] for f in done["failures"]] == [424] * (len(expect_models) - 1)
    result = next(e for e in events if e["type"] == "result")
    assert result["judge"]["policy"] == (policy or None)
    assert result["tips"] == ["one", "two"]


def test_every_judge_failing_ends_with_an_error_event():
    gw = acme_gateway(judge_fail=("meta/llama-3.3-70b-instruct", "mistralai/mistral-small-3.2-24b-instruct-2506"))
    events = events_of(review_with(gw, ACME))
    assert events[-1]["type"] == "error" and events[-1]["status"] == 424


FATAL_POINTS = {
    "scout": lambda p, b: p == "/chat/completions" and "Identify" in b["messages"][0]["content"],
    "extract": lambda p, b: p == "/chat/completions" and "extract data practices" in b["messages"][0]["content"],
    "research": lambda p, b: p == "/chat/completions" and "research desk" in b["messages"][0]["content"],
    "judge": lambda p, b: p == "/chat/completions" and b.get("stream"),
    "policy_fetch": lambda p, b: p == "/fetch" and "privacy" in b["url"],
}


@pytest.mark.parametrize("where", list(FATAL_POINTS))
def test_budget_running_out_anywhere_ends_with_a_budget_error(where):
    gw = acme_gateway(fatal_at=FATAL_POINTS[where])
    events = events_of(review_with(gw, ACME))
    err = events[-1]
    assert err["type"] == "error" and err["code"] == "budget_exceeded"
    assert "budget is used up" in err["message"]
    assert not any(e["type"] == "result" for e in events)


def test_fitbit_like_review_scores_by_code_and_verifies_quotes():
    gw = acme_gateway()
    events = events_of(review_with(gw, ACME, policy="creeping-hunger-judge"))
    result = next(e for e in events if e["type"] == "result")
    assert result["score_by"] == "code"
    factors = {f["name"]: f["point"] for f in result["stats"]["score"]["factors"]}
    assert factors["Sensitive categories"] == 1 and factors["Deletion time"] == 1
    assert result["score"] == 1 + sum(v for v in factors.values() if v in (0, 1))
    assert result["extraction"]["red_flags"][0]["quote_verified"] is True
    assert result["stats"]["sandbox"] == "otari_code_execution"
    done = events[-1]
    assert done["type"] == "done" and done["billed_usd"] is not None and done["budget"]["limit_usd"] == 1.0


def test_sandbox_failure_falls_back_to_the_backend_script():
    events = events_of(review_with(acme_gateway(sandbox_ok=False), ACME))
    result = next(e for e in events if e["type"] == "result")
    assert result["stats"]["sandbox"] == "backend" and result["score_by"] == "code"
    assert any("sandbox failed" in n for n in events[-1]["notes"])


@pytest.mark.parametrize("reply", ['{"sells_data": "no", "red_flags": [{"flag": "x", "quote": "It may', "no json", "```json\n{]\n```"])
def test_malformed_extractor_reply_never_ends_the_review(reply):
    events = events_of(review_with(acme_gateway(extractor_reply=reply), ACME))
    assert events[-1]["type"] == "done"
    assert step(events, "extract", "done")["data"]["partial"] is True


@pytest.mark.parametrize("servers,refuse,mode", [
    ([{"id": "srv-1", "name": "creeping-hunger"}], False, "otari_managed_mcp_stored"),
    ([{"id": "srv-2", "name": "something-else"}], False, "local_fallback"),
    ([], False, "local_fallback"),
    ([{"id": "srv-1", "name": "Creeping Hunger"}], True, "local_fallback"),
])
def test_mcp_modes(servers, refuse, mode):
    events = events_of(review_with(acme_gateway(servers=servers, mcp_refuse=refuse), ACME))
    research = step(events, "research", "done")
    assert research["mcp_mode"] == mode
    facts = research["data"]["facts"]
    assert facts["tosdr"]["source"] == "https://tosdr.org/en/service/9"
    expected_via = "MCP tool called in Otari's loop" if mode.startswith("otari") else "MCP tool (local fallback)"
    assert facts["breaches"]["via"] == expected_via


def test_stored_mcp_id_is_sent_to_otari():
    gw = acme_gateway()
    events_of(review_with(gw, ACME))
    research = [b for p, b in gw.log if p == "/chat/completions" and "research desk" in b["messages"][0]["content"]]
    assert research[0]["mcp_server_ids"] == ["srv-1"]


def test_web_tools_off_reads_pages_locally_and_says_so():
    gw = acme_gateway(web_tools=False)
    r = review_with(gw, ACME, local_pages={ACME: f"<html><title>Acme</title><body>{CLEAN_PAGE}<a href='/privacy'>Privacy</a></body></html>",
                                          "https://acme.test/privacy": f"<html><body><p>{CLEAN_POLICY}</p></body></html>"})
    events = events_of(r)
    assert not any(p in ("/fetch", "/search") for p, _ in gw.log)
    assert step(events, "read", "done")["via"] == "local_fetch"
    assert step(events, "policy", "done")["url"] == "https://acme.test/privacy"
    assert any("disabled" in n for n in events[-1]["notes"])


def test_no_policy_anywhere_reviews_the_page_itself():
    gw = Gateway(pages={ACME: "Acme band. Buy it. " * 10})
    events = events_of(review_with(gw, ACME))
    assert step(events, "policy", "done")["detail"] == "fallback"
    assert events[-1]["type"] == "done"


def test_only_three_policy_candidates_use_paid_otari_fetches():
    gw = Gateway(pages={ACME: "Acme band [privacy](/p1) [privacy](/p2) [privacy](/p3) [privacy](/p4) [privacy](/p5)"})
    events_of(review_with(gw, ACME))
    policy_fetches = [b["url"] for p, b in gw.log if p == "/fetch" and b["url"] != ACME]
    assert len(policy_fetches) == 3


def test_review_events_are_saved_and_a_repeat_visit_replays_them():
    import store
    gw = acme_gateway()
    first = events_of(review_with(gw, ACME))
    calls_after_first = len(gw.log)
    r = Review(ACME, None, None, "unit")
    r.o._c = httpx.AsyncClient(transport=httpx.MockTransport(gw))
    second = events_of(r)
    assert second[0]["cached_from"] == first[0]["review_id"]
    assert [e["type"] for e in second] == [e["type"] for e in first if e["type"] != "token"]
    assert all(p.startswith("/end-users") for p, _ in gw.log[calls_after_first:])
    assert store.list_summaries()[0]["score"] == next(e for e in first if e["type"] == "result")["score"]


def test_internal_crash_is_an_error_event_not_a_broken_stream():
    gw = acme_gateway()
    r = review_with(gw, ACME)

    async def boom(*_a, **_k):
        raise KeyError("surprise")
    r._compute = boom
    events = events_of(r)
    assert events[-1]["type"] == "error" and events[-1]["code"] == "internal" and "KeyError" in events[-1]["message"]


@pytest.mark.parametrize("err,expect_otari", [
    (OtariError(403, "web_access_disabled", "off"), False),
    (OtariError(404, None, "fetch failed"), False),
    (OtariError(504, "gateway_timeout", "slow"), False),
])
def test_read_url_falls_back_to_the_backend_client(err, expect_otari):
    r = review_with(Gateway(), "https://shop.test/p", local_pages={"https://shop.test/p": "<html><body>hello page</body></html>"})

    async def fail(_url):
        raise err
    r.o.fetch = fail
    text, html, via = asyncio.run(r.read_url("https://shop.test/p"))
    assert (text, via) == ("hello page", "local_fetch")
    assert r.web_access is (err.code != "web_access_disabled")


@pytest.mark.parametrize("code", ["budget_exceeded", "insufficient_funds"])
def test_read_url_does_not_hide_budget_errors(code):
    r = review_with(Gateway(), "https://shop.test/p")

    async def fail(_url):
        raise OtariError(402, code, "out")
    r.o.fetch = fail
    with pytest.raises(OtariError):
        asyncio.run(r.read_url("https://shop.test/p"))


@pytest.mark.parametrize("key", ["content", "text", "markdown"])
def test_read_url_accepts_each_fetch_field(key):
    r = review_with(Gateway(), "https://shop.test/p")

    async def ok(_url):
        return {key: "fetched words"}, {}
    r.o.fetch = ok
    assert asyncio.run(r.read_url("https://shop.test/p")) == ("fetched words", "", "otari_fetch")
