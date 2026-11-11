"""The Otari client against a fake gateway: error shapes, retries, the user field, streaming and budgets."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import otari
from otari import Otari, OtariError, _meta, _raise, cost_of, message_text


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(otari.asyncio, "sleep", instant)


def client(handler, **kw) -> tuple[Otari, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request):
        seen.append(request)
        return handler(request, len(seen))
    o = Otari(**kw)
    o._c = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    return o, seen


def run(coro):
    return asyncio.run(coro)


ERROR_BODIES = [
    (403, {"detail": "Budget exceeded", "code": "budget_exceeded"}, "budget_exceeded", "Budget exceeded"),
    (403, {"detail": {"code": "user_blocked", "message": "blocked"}}, "user_blocked", "blocked"),
    (402, {"error": {"code": "insufficient_funds", "message": "no credit"}}, "insufficient_funds", "no credit"),
    (400, {"error": {"type": "invalid_request_error", "message": "bad"}}, "invalid_request_error", "bad"),
    (424, {"detail": "model unavailable"}, None, "model unavailable"),
    (422, {"detail": [{"loc": ["body"], "msg": "x"}]}, None, "[{'loc': ['body'], 'msg': 'x'}]"),
    (500, ["weird"], None, "['weird']"),
    (404, {"detail": {"message": "nope"}, "code": "not_found"}, "not_found", "nope"),
    (403, {"detail": {"reason": "guard"}}, None, '{"reason": "guard"}'),
]


@pytest.mark.parametrize("status,body,code,detail", ERROR_BODIES)
def test_error_bodies_become_one_error_shape(status, body, code, detail):
    r = httpx.Response(status, json=body, headers={"otari-request-id": "rid"})
    with pytest.raises(OtariError) as e:
        _raise(r)
    assert (e.value.status, e.value.code, e.value.detail) == (status, code, detail)
    assert e.value.meta == {"otari-request-id": "rid"}


@pytest.mark.parametrize("status", [500, 502, 503, 504, 520])
@pytest.mark.parametrize("body,ctype", [
    (b"<!DOCTYPE html><html><body>nginx</body></html>", "text/html"),
    (b"<html><body>cloudflare</body></html>", "text/plain"),
    (b"  <!doctype HTML><p>x</p>", ""),
    (b"<h1>Bad gateway</h1><p>sorry</p>", "text/plain"),
])
def test_html_error_pages_never_reach_the_user(status, body, ctype):
    with pytest.raises(OtariError) as e:
        _raise(httpx.Response(status, content=body, headers={"content-type": ctype}))
    assert e.value.code == "gateway_error"
    assert "<" not in e.value.friendly


@pytest.mark.parametrize("code,needle", [
    ("budget_exceeded", "budget is used up"), ("user_blocked", "blocked"), ("guardrail_violation", "guardrail"),
    ("insufficient_funds", "out of credit"), ("pricing_required", "out of credit"), ("web_access_disabled", "turned off"),
    ("gateway_error", "gateway error"), ("gateway_timeout", "gateway error"),
])
def test_friendly_messages(code, needle):
    assert needle in OtariError(400, code, "raw").friendly


@pytest.mark.parametrize("status", [502, 503, 504])
def test_friendly_for_gateway_statuses(status):
    assert OtariError(status, None, "x").friendly == f"{status} Otari gateway error"


def test_friendly_falls_back_to_short_detail():
    assert OtariError(400, None, "y" * 1000).friendly == "y" * 300


@pytest.mark.parametrize("headers,expected", [
    ({"otari-model": "m", "x-other": "z"}, {"otari-model": "m"}),
    ({"otari-guardrails": '[{"profile": "p", "valid": true}]'}, {"otari-guardrails": [{"profile": "p", "valid": True}]}),
    ({"otari-guardrails": "not json"}, {"otari-guardrails": "not json"}),
    ({"otari-fallback": "true", "otari-attempt-count": "2"}, {"otari-fallback": "true", "otari-attempt-count": "2"}),
    ({}, {}),
])
def test_meta_headers(headers, expected):
    assert _meta(httpx.Headers(headers)) == expected


@pytest.mark.parametrize("flaky_status", [502, 503, 504])
def test_one_retry_on_a_gateway_hiccup(flaky_status):
    o, seen = client(lambda req, n: httpx.Response(flaky_status if n == 1 else 200, json={"ok": n}))
    j, _ = run(o.search("q"))
    assert j == {"ok": 2} and len(seen) == 2


@pytest.mark.parametrize("flaky_status", [502, 503, 504])
def test_two_gateway_failures_raise(flaky_status):
    o, seen = client(lambda req, n: httpx.Response(flaky_status, json={"detail": "down"}))
    with pytest.raises(OtariError) as e:
        run(o.fetch("https://x.test"))
    assert e.value.status == flaky_status and len(seen) == 2


@pytest.mark.parametrize("exc", [httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout])
def test_network_errors_retry_once_then_become_504(exc):
    def handler(req, n):
        raise exc("boom", request=req)
    o, seen = client(handler)
    with pytest.raises(OtariError) as e:
        run(o.chat(model="m", messages=[]))
    assert (e.value.status, e.value.code, len(seen)) == (504, "gateway_timeout", 2)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 424, 429])
def test_client_errors_are_not_retried(status):
    o, seen = client(lambda req, n: httpx.Response(status, json={"detail": "no"}))
    with pytest.raises(OtariError):
        run(o.chat(model="m", messages=[]))
    assert len(seen) == 1


USER_REFUSED = {"detail": "The 'user' field requires a service key"}


def test_user_field_refusal_drops_the_field_and_retries():
    def handler(req, n):
        body = json.loads(req.content)
        return httpx.Response(403, json=USER_REFUSED) if "user" in body else httpx.Response(200, json={"ok": True})
    o, seen = client(handler, end_user="ch-install:abc", send_end_user=True)
    j, _ = run(o.chat(model="m", messages=[]))
    assert j == {"ok": True}
    assert [("user" in json.loads(r.content)) for r in seen] == [True, False]
    assert o.send_end_user is False and any("service key" in n for n in o.notes)


@pytest.mark.parametrize("send,end_user,has_user", [(True, "ch-install:a", True), (False, "ch-install:a", False), (True, None, False)])
def test_user_field_is_sent_only_when_configured(send, end_user, has_user):
    o, seen = client(lambda req, n: httpx.Response(200, json={}), end_user=end_user, send_end_user=send)
    run(o.search("q"))
    assert ("user" in json.loads(seen[0].content)) is has_user


def test_headers_carry_key_and_conversation_without_logging_the_key():
    o, seen = client(lambda req, n: httpx.Response(200, json={}), conversation_id="ch-1")
    run(o.search("q"))
    assert seen[0].headers["Otari-Conversation-Id"] == "ch-1"
    assert seen[0].headers["Otari-Key"]
    assert seen[0].url.path.endswith("/search")


def test_missing_key_stops_before_any_request(monkeypatch):
    monkeypatch.delenv("OTARI_API_KEY")
    o, seen = client(lambda req, n: httpx.Response(200, json={}))
    with pytest.raises(RuntimeError, match="OTARI_API_KEY is not set"):
        run(o.search("q"))
    assert not seen


def sse(*chunks: str) -> bytes:
    return "".join(f"data: {c}\n\n" for c in chunks).encode()


def collect(o, **body):
    async def go():
        return [p async for p in o.chat_stream(**body)]
    return run(go())


@pytest.mark.parametrize("chunks,text,usage", [
    ([json.dumps({"choices": [{"delta": {"content": "Hel"}}]}), json.dumps({"choices": [{"delta": {"content": "lo"}}]}), "[DONE]"], "Hello", {}),
    ([json.dumps({"choices": [{"delta": {"content": "A"}}]}), json.dumps({"choices": [], "usage": {"cost_usd": 0.01}}), "[DONE]"], "A", {"cost_usd": 0.01}),
    (["not json", json.dumps({"choices": [{"delta": {}}]}), json.dumps({"choices": [{"delta": {"content": "x"}}]})], "x", {}),
    ([json.dumps({"choices": [{"delta": {"content": "a"}}]}), "[DONE]", json.dumps({"choices": [{"delta": {"content": "late"}}]})], "a", {}),
    ([], "", {}),
])
def test_stream_parsing(chunks, text, usage):
    o, seen = client(lambda req, n: httpx.Response(200, content=sse(*chunks), headers={"otari-model": "llama"}))
    parts = collect(o, model="m", messages=[])
    assert parts[0] == {"meta": {"otari-model": "llama"}}
    assert "".join(p.get("delta", "") for p in parts) == text
    assert parts[-1] == {"usage": usage}
    body = json.loads(seen[0].content)
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize("err", [{"code": "model_error", "message": "died"}, "plain string error"])
def test_error_inside_the_stream_raises(err):
    o, _ = client(lambda req, n: httpx.Response(200, content=sse(json.dumps({"choices": [{"delta": {"content": "a"}}]}), json.dumps({"error": err}))))
    with pytest.raises(OtariError) as e:
        collect(o, model="m", messages=[])
    assert e.value.status == 500


@pytest.mark.parametrize("status,code", [(424, None), (404, "model_not_found"), (403, "budget_exceeded"), (500, None)])
def test_stream_http_errors_raise_before_any_token(status, code):
    o, _ = client(lambda req, n: httpx.Response(status, json={"detail": "x", "code": code}))
    with pytest.raises(OtariError) as e:
        collect(o, model="m", messages=[])
    assert (e.value.status, e.value.code) == (status, code)


def test_stream_user_refusal_retries_without_user():
    def handler(req, n):
        body = json.loads(req.content)
        if "user" in body:
            return httpx.Response(403, json=USER_REFUSED)
        return httpx.Response(200, content=sse(json.dumps({"choices": [{"delta": {"content": "ok"}}]})))
    o, seen = client(handler, end_user="ch-install:a", send_end_user=True)
    parts = collect(o, model="m", messages=[])
    assert "".join(p.get("delta", "") for p in parts) == "ok" and len(seen) == 2


@pytest.mark.parametrize("rows,spend,remaining,blocked", [
    ([{"spend": 0.25, "next_budget_reset_at": "2026-11-12T00:00:00Z", "blocked": False, "current_requests": 3}], 0.25, 0.75, False),
    ([{"spend": 1.5, "blocked": True}], 1.5, 0.0, True),
    ([{}], 0.0, 1.0, False),
    ([], 0.0, 1.0, False),
    ([{"spend": None}], 0.0, 1.0, False),
])
def test_end_user_budget(rows, spend, remaining, blocked):
    o, seen = client(lambda req, n: httpx.Response(200, json=rows), end_user="ch-install:a", send_end_user=True)
    b = run(o.end_user_budget())
    assert (b["spend_usd"], b["remaining_usd"], b["blocked"], b["limit_usd"]) == (spend, remaining, blocked, 1.0)
    assert seen[0].url.params["external_id"] == "ch-install:a"


@pytest.mark.parametrize("response", [httpx.Response(403, json={"detail": "Invalid master key"}), httpx.Response(200, json={"data": []}),
                                      httpx.Response(200, content=b"not json"), httpx.Response(500, content=b"<html></html>")])
def test_end_user_budget_unreadable_is_none(response):
    o, _ = client(lambda req, n: response, end_user="ch-install:a", send_end_user=True)
    assert run(o.end_user_budget()) is None


@pytest.mark.parametrize("end_user,send", [(None, True), ("ch-install:a", False)])
def test_end_user_budget_off_makes_no_call(end_user, send):
    o, seen = client(lambda req, n: httpx.Response(200, json=[]), end_user=end_user, send_end_user=send)
    assert run(o.end_user_budget()) is None and not seen


@pytest.mark.parametrize("limit", ["0.05", "1.00", "2.5"])
def test_budget_limit_follows_the_env(monkeypatch, limit):
    monkeypatch.setenv("END_USER_BUDGET_USD", limit)
    o, _ = client(lambda req, n: httpx.Response(200, json=[{"spend": 0.01}]), end_user="u", send_end_user=True)
    assert run(o.end_user_budget())["limit_usd"] == float(limit)


@pytest.mark.parametrize("value,cost", [
    (None, 0.0), ({}, 0.0), ({"usage": {"cost_usd": 0.002}}, 0.002), ({"cost_usd": "0.5"}, 0.5), ({"usage": {"cost_usd": "abc"}}, 0.0),
    ({"usage": {"cost_usd": None}}, 0.0), ({"usage": {}}, 0.0),
])
def test_cost_of(value, cost):
    assert cost_of(value) == cost


@pytest.mark.parametrize("resp,text", [
    ({"choices": [{"message": {"content": "hi"}}]}, "hi"), ({"choices": [{"message": {"content": None}}]}, ""),
    ({"choices": []}, ""), ({}, ""), ({"choices": [{"message": {}}]}, ""),
])
def test_message_text(resp, text):
    assert message_text(resp) == text


@pytest.mark.parametrize("method,path,args", [("search", "/search", ("q",)), ("fetch", "/fetch", ("https://x.test",)),
                                              ("code_execute", "/code/execute", ("print(1)",))])
def test_endpoint_paths_and_bodies(method, path, args):
    o, seen = client(lambda req, n: httpx.Response(200, json={"ok": True}))
    run(getattr(o, method)(*args))
    assert seen[0].url.path == "/api/v1" + path
    assert seen[0].method == "POST"
