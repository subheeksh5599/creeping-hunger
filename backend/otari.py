"""Thin async client for the Otari gateway (OpenAI-compatible + Otari extras).

The API key is read from the OTARI_API_KEY environment variable only. It is never
logged, printed or returned to the browser.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

BASE_URL = os.getenv("OTARI_BASE_URL", "https://otari.ai/api/v1").rstrip("/")
META_HEADERS = (
    "otari-model", "otari-provider", "otari-fallback", "otari-attempt-count",
    "otari-guardrails", "otari-request-id", "otari-end-user-budget", "otari-response-duration-ms",
)


class OtariError(Exception):
    def __init__(self, status: int, code: str | None, detail: str, meta: dict | None = None):
        super().__init__(f"{status} {code or ''} {detail}".strip())
        self.status, self.code, self.detail, self.meta = status, code, detail, meta or {}

    @property
    def friendly(self) -> str:
        if self.code == "budget_exceeded":
            return "You've used today's free reviews. Come back tomorrow (your per-install budget resets daily)."
        if self.code == "user_blocked":
            return "This install has been blocked from making reviews."
        if self.code == "guardrail_violation":
            return "Blocked by the prompt-injection guardrail: this page tried to give our AI orders."
        if self.code in ("insufficient_funds", "pricing_required"):
            return "The Otari workspace is out of credit."
        if self.code == "web_access_disabled":
            return "Web search/fetch is turned off for this Otari workspace."
        if self.status in (502, 503, 504) or self.code in ("gateway_error", "gateway_timeout"):
            return f"{self.status} Otari gateway error"
        if "<" in (self.detail or "") and "</" in self.detail:
            return f"{self.status} Otari gateway error"
        return self.detail[:300]


def _key() -> str:
    k = os.getenv("OTARI_API_KEY")
    if not k:
        raise RuntimeError("OTARI_API_KEY is not set. export OTARI_API_KEY=... (never commit it)")
    return k


def _meta(h: httpx.Headers) -> dict:
    out = {k: h.get(k) for k in META_HEADERS if h.get(k) is not None}
    if "otari-guardrails" in out:
        try:
            out["otari-guardrails"] = json.loads(out["otari-guardrails"])
        except ValueError:
            pass
    return out


def _is_html(raw: bytes, headers: httpx.Headers) -> bool:
    ct = (headers.get("content-type") or "").lower()
    if "text/html" in ct or "application/xhtml" in ct:
        return True
    head = raw.lstrip()[:32].lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _raise(r: httpx.Response, body: bytes | None = None) -> None:
    raw = body if body is not None else r.content
    if _is_html(raw, r.headers):
        raise OtariError(r.status_code, "gateway_error", "Otari gateway error", _meta(r.headers))
    try:
        j = json.loads(raw)
        detail = j.get("detail") if isinstance(j, dict) else str(j)
        code = j.get("code") if isinstance(j, dict) else None
        if isinstance(detail, dict):
            code = code or detail.get("code")
            detail = detail.get("message") or json.dumps(detail)
        if isinstance(j, dict) and "error" in j and isinstance(j["error"], dict):
            code = code or j["error"].get("code") or j["error"].get("type")
            detail = detail or j["error"].get("message")
    except ValueError:
        code, detail = None, raw[:300].decode(errors="replace")
        if "<" in detail and "</" in detail:
            code, detail = "gateway_error", "Otari gateway error"
    raise OtariError(r.status_code, code, str(detail or r.reason_phrase), _meta(r.headers))


@dataclass
class Otari:
    conversation_id: str | None = None
    end_user: str | None = None          # anonymous install id (per-user budgets)
    send_end_user: bool = field(default_factory=lambda: os.getenv("OTARI_SEND_END_USER", "1") == "1")
    notes: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._c = httpx.AsyncClient(timeout=httpx.Timeout(180, connect=20))

    async def aclose(self):
        await self._c.aclose()

    def _headers(self) -> dict:
        h = {"Otari-Key": _key(), "Content-Type": "application/json"}
        if self.conversation_id:
            h["Otari-Conversation-Id"] = self.conversation_id
        return h

    def _with_user(self, body: dict) -> dict:
        if self.end_user and self.send_end_user:
            body = {**body, "user": self.end_user}
        return body

    def _user_mismatch(self, e: OtariError) -> bool:
        return e.status == 403 and "'user' field" in e.detail

    def _disable_user(self):
        self.send_end_user = False
        self.notes.append("This API key is not a service key, so per-install budgets are off "
                          "(Otari refused the `user` field). See README › Dashboard steps.")

    async def _send(self, method: str, path: str, body: dict | None = None) -> httpx.Response:
        retried = False
        while True:
            try:
                if method == "POST":
                    r = await self._c.post(f"{BASE_URL}{path}", headers=self._headers(),
                                           json=self._with_user(body or {}))
                else:
                    r = await self._c.get(f"{BASE_URL}{path}", headers=self._headers())
            except (httpx.TimeoutException, httpx.ConnectError):
                if retried:
                    raise OtariError(504, "gateway_timeout", "Otari gateway error")
                retried = True
                await asyncio.sleep(2)
                continue
            if r.status_code in (502, 503, 504) and not retried:
                retried = True
                await asyncio.sleep(2)
                continue
            return r

    async def _post(self, path: str, body: dict) -> tuple[dict, dict]:
        for _ in range(2):
            r = await self._send("POST", path, body)
            if r.status_code >= 400:
                try:
                    _raise(r)
                except OtariError as e:
                    if self._user_mismatch(e) and self.send_end_user:
                        self._disable_user()
                        continue
                    raise
            return r.json(), _meta(r.headers)
        raise RuntimeError("unreachable")

    async def get(self, path: str) -> dict:
        r = await self._send("GET", path)
        if r.status_code >= 400:
            _raise(r)
        return r.json()

    # --- endpoints -------------------------------------------------------
    async def chat(self, **body: Any) -> tuple[dict, dict]:
        return await self._post("/chat/completions", body)

    async def chat_stream(self, **body: Any) -> AsyncIterator[dict]:
        """Yields {"meta":...} first, then {"delta": str} chunks, then {"usage":..., "otari_tool_calls":...}."""
        body = {**body, "stream": True, "stream_options": {"include_usage": True}}
        for _ in range(2):
            async with self._c.stream("POST", f"{BASE_URL}/chat/completions",
                                      headers=self._headers(), json=self._with_user(body)) as r:
                if r.status_code >= 400:
                    raw = await r.aread()
                    try:
                        _raise(r, raw)
                    except OtariError as e:
                        if self._user_mismatch(e) and self.send_end_user:
                            self._disable_user()
                            continue
                        raise
                yield {"meta": _meta(r.headers)}
                usage = None
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if "error" in chunk:
                        err = chunk["error"] if isinstance(chunk["error"], dict) else {"message": str(chunk["error"])}
                        raise OtariError(500, err.get("code"), err.get("message", "stream error"))
                    for ch in chunk.get("choices") or []:
                        txt = (ch.get("delta") or {}).get("content")
                        if txt:
                            yield {"delta": txt}
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                yield {"usage": usage or {}}
                return

    async def search(self, query: str, max_results: int = 5) -> tuple[dict, dict]:
        return await self._post("/search", {"query": query, "max_results": max_results})

    async def fetch(self, url: str) -> tuple[dict, dict]:
        return await self._post("/fetch", {"url": url})

    async def code_execute(self, code: str, timeout_seconds: int = 30) -> tuple[dict, dict]:
        return await self._post("/code/execute", {"code": code, "timeout_seconds": timeout_seconds})


def message_text(resp: dict) -> str:
    try:
        return resp["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError):
        return ""


def cost_of(resp_or_usage: dict | None) -> float:
    if not resp_or_usage:
        return 0.0
    u = resp_or_usage.get("usage", resp_or_usage)
    try:
        return float(u.get("cost_usd") or 0)
    except (TypeError, ValueError):
        return 0.0
