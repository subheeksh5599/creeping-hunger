"""The MCP research tools against fake HIBP, ToS;DR and Wayback responses."""
from __future__ import annotations

import httpx
import pytest

import pipeline

mcp = pipeline.mcp_tools


def fake(monkeypatch, handler):
    seen: list[httpx.Request] = []

    def wrapped(req):
        seen.append(req)
        return handler(req)
    monkeypatch.setattr(mcp, "_client", lambda: httpx.Client(transport=httpx.MockTransport(wrapped), follow_redirects=True))
    return seen


@pytest.mark.parametrize("value,root", [
    ("ring.com", "ring.com"), ("https://www.ring.com/x", "ring.com"), ("shop.bbc.co.uk", "bbc.co.uk"), ("x.org.au", "x.org.au"),
    ("store.example.net.in", "example.net.in"), ("HTTP://A.B.C.D.COM:8080/p", "d.com"), ("solo", "solo"), ("  fitbit.com  ", "fitbit.com"),
])
def test_root_domain(value, root):
    assert mcp._root_domain(value) == root


@pytest.mark.parametrize("value,slug", [
    ("Ring Video Doorbell", "ring-video-doorbell"), ("  Fitbit   Charge 6 ", "fitbit-charge-6"), ("Café!", "caf"), ("", ""),
    ("A&B / C", "a-b-c"), ("---x---", "x"),
])
def test_slugify(value, slug):
    assert mcp._slugify(value) == slug


@pytest.mark.parametrize("html,text", [
    ("<p>Hi&nbsp;there</p>", "Hi there"), ("<script>x</script>a", "a"), ("a\n\n  b", "a b"), ("<svg><g/></svg>ok", "ok"),
])
def test_strip_html(html, text):
    assert mcp._strip_html(html) == text


HIBP_ROWS = [{"Name": f"Breach{i}", "BreachDate": f"20{10 + i}-01-01", "PwnCount": 1000 * i, "DataClasses": ["Email"] * 12} for i in range(12)]


@pytest.mark.parametrize("rows,count,first", [([], 0, None), (HIBP_ROWS[:1], 1, "Breach0"), (HIBP_ROWS, 12, "Breach0")])
def test_hibp_rows(monkeypatch, rows, count, first):
    seen = fake(monkeypatch, lambda req: httpx.Response(200, json=rows))
    out = mcp.hibp_breaches_impl("https://www.fitbit.com/p")
    assert out["domain"] == "fitbit.com" and out["breach_count"] == count
    assert len(out["breaches"]) == min(10, count)
    assert all(len(b["data_classes"]) <= 8 for b in out["breaches"])
    if first:
        assert out["breaches"][0]["name"] == first
    assert seen[0].url.params["domain"] == "fitbit.com"


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(429), httpx.Response(200, content=b"<html>")])
def test_hibp_failure_is_a_row_error_not_a_crash(monkeypatch, response):
    fake(monkeypatch, lambda req: response)
    out = mcp.hibp_breaches_impl("fitbit.com")
    assert out["error"].startswith("lookup failed")


def tosdr_handler(services, rating="D", points=20):
    def handler(req):
        if "search" in req.url.path:
            return httpx.Response(200, json={"services": services})
        return httpx.Response(200, json={"name": "Fitbit", "rating": rating, "points": [{"title": f"p{i}"} for i in range(points)]})
    return handler


@pytest.mark.parametrize("query,services,picked", [
    ("fitbit.com", [{"id": 1, "urls": ["other.com"]}, {"id": 2, "urls": ["www.fitbit.com"]}], 2),
    ("fitbit.com", [{"id": 7, "urls": ["nope.com"]}], 7),
    ("Fitbit", [{"id": 3, "urls": []}], 3),
])
def test_tosdr_picks_the_matching_service(monkeypatch, query, services, picked):
    fake(monkeypatch, tosdr_handler(services))
    out = mcp.tosdr_impl(query)
    assert out["found"] is True and out["url"] == f"https://tosdr.org/en/service/{picked}"
    assert out["grade"] == "D" and len(out["points"]) == 15


def test_tosdr_nothing_found(monkeypatch):
    fake(monkeypatch, tosdr_handler([]))
    assert mcp.tosdr_impl("unknown.example") == {"query": "unknown.example", "found": False}


def test_tosdr_failure(monkeypatch):
    fake(monkeypatch, lambda req: httpx.Response(503))
    assert mcp.tosdr_impl("fitbit.com")["error"].startswith("lookup failed")


PNI_PAGE = ("<html><body><h1>Fitbit</h1><p>*privacy not included with this product</p><p>People voted: Very creepy</p>"
            "<p>Review date: Nov. 8, 2023</p><h2>What could happen if something goes wrong?</h2><p>Bad things.</p></body></html>")


def pni_handler(available_slug, page=PNI_PAGE):
    def handler(req):
        if "wayback/available" in str(req.url):
            hit = req.url.params["url"].rstrip("/").endswith(available_slug)
            snap = {"available": True, "url": f"http://web.archive.org/web/20231108000000/https://x/{available_slug}/",
                    "timestamp": "20231108000000"} if hit else None
            return httpx.Response(200, json={"archived_snapshots": {"closest": snap} if snap else {}})
        assert "id_/" in str(req.url) and str(req.url).startswith("https://")
        return httpx.Response(200, text=page)
    return handler


@pytest.mark.parametrize("brand,product,slug", [
    ("Fitbit", "Charge 6", "fitbit-charge-6"), ("Fitbit", "Charge 6 Fitness Tracker", "fitbit-charge-6"),
    ("Ring", "Video Doorbell Pro 2", "ring-video-doorbell"), ("Garmin", "", "garmin"),
])
def test_pni_archive_finds_the_slug_and_reads_the_rows(monkeypatch, brand, product, slug):
    fake(monkeypatch, pni_handler(slug))
    out = mcp.pni_archive_impl(brand, product)
    assert out["found"] is True and out["slug"] == slug
    assert (out["pni_warning_label"], out["people_voted"], out["review_date"]) == (True, "Very creepy", "Nov. 8, 2023")
    assert out["snapshot_date"] == "20231108"
    assert out["excerpt"].startswith("What could happen")


def test_pni_archive_without_the_label_or_votes(monkeypatch):
    fake(monkeypatch, pni_handler("acme", page="<p>A fine product.</p>"))
    out = mcp.pni_archive_impl("Acme")
    assert (out["pni_warning_label"], out["people_voted"], out["review_date"]) == (False, None, None)


def test_pni_archive_not_found_lists_what_it_tried(monkeypatch):
    fake(monkeypatch, pni_handler("never"))
    out = mcp.pni_archive_impl("Acme", "Thing One Two Three")
    assert out["found"] is False and len(out["tried"]) <= 8 and out["tried"][0] == "acme-thing-one-two-three"


def test_pni_archive_network_failure(monkeypatch):
    fake(monkeypatch, lambda req: httpx.Response(500, content=b"x"))
    assert mcp.pni_archive_impl("Acme")["found"] is False


def test_mcp_tools_are_registered_with_the_three_names():
    import asyncio
    assert {t.name for t in asyncio.run(mcp.mcp.list_tools())} == {"hibp_breaches", "tosdr", "pni_archive"}


def test_mcp_tool_call_goes_through_the_impl(monkeypatch):
    import asyncio
    fake(monkeypatch, lambda req: httpx.Response(200, json=HIBP_ROWS[:2]))
    result = asyncio.run(mcp.mcp.call_tool("hibp_breaches", {"domain": "fitbit.com"}))
    assert "Breach1" in str(result)


@pytest.mark.parametrize("via_in_loop", [set(), {"hibp_breaches"}, {"hibp_breaches", "tosdr", "pni_archive"}])
def test_tool_rows_credit_the_loop_only_for_tools_it_ran(via_in_loop):
    via = lambda n: "loop" if n in via_in_loop else "backend"  # noqa: E731
    out = pipeline.tool_facts({"breaches": []}, {"found": False}, {"found": False}, via)
    for key, tool in (("breaches", "hibp_breaches"), ("tosdr", "tosdr"), ("pni", "pni_archive")):
        assert out["facts"][key]["via"] == ("loop" if tool in via_in_loop else "backend")
    assert out["facts"]["breaches"]["source"] == "https://haveibeenpwned.com/PwnedWebsites"
    assert "tosdr_grade" not in out


@pytest.mark.parametrize("hibp,tosdr,pni", [
    ({"error": "lookup failed: X"}, {"error": "lookup failed: Y"}, {"error": "lookup failed: Z"}),
    ({"breaches": None}, {"found": True, "grade": None}, {"found": True, "people_voted": None}),
])
def test_tool_rows_with_failed_lookups(hibp, tosdr, pni):
    out = pipeline.tool_facts(hibp, tosdr, pni, lambda n: "b")
    assert out["breaches"] == [] and "tosdr_grade" not in out and "pni_people_voted" not in out
    assert out["facts"]["breaches"]["error"] == hibp.get("error")


@pytest.mark.parametrize("extraction,research,blocked,expected", [
    ({}, {}, False, {"sensitive": [], "retention": "", "pni_warning": False, "breaches": 0, "blocked": False}),
    ({"sensitive_data": "health"}, {}, False, {"sensitive": [], "retention": "", "pni_warning": False, "breaches": 0, "blocked": False}),
    ({"sensitive_data": list("abcdefghijkl"), "retention": "x" * 900}, {"breaches": [1, 2]}, True,
     {"sensitive": list("abcdefghij"), "retention": "x" * 600, "pni_warning": False, "breaches": 2, "blocked": True}),
    ({"sensitive_data": [1, None]}, {"pni_warning_label": True, "breaches": None}, False,
     {"sensitive": ["1", "None"], "retention": "", "pni_warning": True, "breaches": 0, "blocked": False}),
    ({"blocked": True, "reason": "prompt_injection"}, {}, True, {"sensitive": [], "retention": "", "pni_warning": False, "breaches": 0, "blocked": True}),
])
def test_score_facts(extraction, research, blocked, expected):
    assert pipeline.score_facts(extraction, research, blocked) == expected
