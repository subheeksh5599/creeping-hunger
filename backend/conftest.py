"""Every test runs offline: Otari points at a closed port and real HTTP transports refuse to connect."""
from __future__ import annotations

import os

os.environ["OTARI_API_KEY"] = "offline-test-key"
os.environ["OTARI_BASE_URL"] = "http://127.0.0.1:9/api/v1"
for name in ("PUBLIC_BASE_URL", "MCP_PUBLIC_URL", "MCP_SERVER_ID", "JUDGE_POLICY", "GUARDRAIL_TOKEN", "OTARI_SERVICE_KEY"):
    os.environ.pop(name, None)

import httpx  # noqa: E402
import pytest  # noqa: E402

ATTEMPTS: list[str] = []


class NetworkBlocked(RuntimeError):
    pass


def _refuse_sync(self, request):
    ATTEMPTS.append(str(request.url))
    raise NetworkBlocked(f"real network call in a test: {request.url}")


async def _refuse_async(self, request):
    ATTEMPTS.append(str(request.url))
    raise NetworkBlocked(f"real network call in a test: {request.url}")


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path):
    import store
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _refuse_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _refuse_async)
    monkeypatch.setattr(store, "DIR", tmp_path / "reviews")
    ATTEMPTS.clear()
    yield
    assert not ATTEMPTS, f"tests must not touch the network: {ATTEMPTS}"
