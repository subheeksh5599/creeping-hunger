"""Creeping Hunger MCP server: privacy-research tools Otari's tool loop can call.

Tools
- hibp_breaches(domain): public breach history from Have I Been Pwned (no key needed)
- tosdr(domain_or_name): Terms of Service; Didn't Read grade + notable points
- pni_archive(brand, product): Mozilla's sunset *Privacy Not Included* review, via the Wayback Machine

Run:  python mcp_server/server.py            (streamable HTTP on :$MCP_PORT or $PORT, default 8765, at /mcp; GET /healthz)
"""
from __future__ import annotations

import os
import re
from html import unescape

import httpx
from fastmcp import FastMCP

UA = {"User-Agent": "creeping-hunger/0.1 (+https://github.com/subheeksh5599/creeping-hunger)"}
mcp = FastMCP("creeping-hunger-research")


def _client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=25, follow_redirects=True,
                        transport=httpx.HTTPTransport(retries=3))


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _root_domain(d: str) -> str:
    d = d.lower().strip()
    d = re.sub(r"^https?://", "", d).split("/")[0].split(":")[0]
    parts = d.split(".")
    if len(parts) > 2 and parts[-2] in {"co", "com", "org", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else d


def hibp_breaches_impl(domain: str) -> dict:
    dom = _root_domain(domain)
    try:
        with _client() as c:
            r = c.get("https://haveibeenpwned.com/api/v3/breaches", params={"domain": dom})
            r.raise_for_status()
            rows = r.json()
    except Exception as e:  # noqa: BLE001
        return {"domain": dom, "error": f"lookup failed: {type(e).__name__}"}
    return {
        "domain": dom,
        "breach_count": len(rows),
        "breaches": [
            {
                "name": b.get("Name"),
                "date": b.get("BreachDate"),
                "pwned_accounts": b.get("PwnCount"),
                "data_classes": b.get("DataClasses", [])[:8],
            }
            for b in rows[:10]
        ],
        "source": "https://haveibeenpwned.com",
    }


def tosdr_impl(domain_or_name: str) -> dict:
    q = domain_or_name.strip()
    dom = _root_domain(q) if "." in q else None
    try:
        with _client() as c:
            name_q = dom.split(".")[0] if dom else q
            r = c.get("https://api.tosdr.org/search/v5/", params={"query": name_q})
            r.raise_for_status()
            services = r.json().get("services", [])
            pick = None
            if dom:
                pick = next((s for s in services if any(_root_domain(u) == dom for u in s.get("urls", []))), None)
            pick = pick or (services[0] if services else None)
            if not pick:
                return {"query": q, "found": False}
            d = c.get("https://api.tosdr.org/service/v3/", params={"id": pick["id"]}).json()
    except Exception as e:  # noqa: BLE001
        return {"query": q, "error": f"lookup failed: {type(e).__name__}"}
    points = d.get("points", [])
    return {
        "query": q,
        "found": True,
        "service": d.get("name"),
        "grade": d.get("rating"),
        "grade_scale": "A (best) .. E (worst); N/A = not yet graded",
        "points": [p.get("title") for p in points[:15]],
        "url": f"https://tosdr.org/en/service/{pick['id']}",
    }


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pni_archive_impl(brand: str, product: str = "") -> dict:
    base = "foundation.mozilla.org/en/privacynotincluded/"
    cands = []
    for s in [f"{brand} {product}", product, brand]:
        slug = _slugify(s)
        if slug and slug not in cands:
            cands.append(slug)
    # also try trimming the product name word by word ("ring video doorbell pro 2" -> "ring video doorbell")
    words = _slugify(f"{brand} {product}").split("-")
    for n in range(len(words) - 1, 1, -1):
        s = "-".join(words[:n])
        if s not in cands:
            cands.append(s)
    try:
        with _client() as c:
            for slug in cands[:8]:
                r = c.get("https://archive.org/wayback/available", params={"url": base + slug + "/"})
                snap = r.json().get("archived_snapshots", {}).get("closest")
                if not snap or not snap.get("available"):
                    continue
                raw_url = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap["url"]).replace("http://", "https://", 1)
                page = c.get(raw_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) creeping-hunger"})
                text = _strip_html(page.text)
                warn = "privacy not included with this product" in text.lower()
                m = re.search(r"People voted:\s*(Not creepy|A little creepy|Somewhat creepy|Very creepy|Super creepy)", text, re.I)
                rd = re.search(r"Review date:\s*([A-Za-z.]+ \d{1,2}, \d{4})", text)
                start = max(0, text.lower().find("what could happen"))
                return {
                    "found": True,
                    "slug": slug,
                    "snapshot": snap["url"],
                    "snapshot_date": snap["timestamp"][:8],
                    "pni_warning_label": warn,
                    "people_voted": m.group(1) if m else None,
                    "review_date": rd.group(1) if rd else None,
                    "excerpt": text[start : start + 1500] if start else text[:1500],
                }
    except Exception as e:  # noqa: BLE001
        return {"found": False, "error": f"lookup failed: {type(e).__name__}", "tried": cands[:8]}
    return {"found": False, "tried": cands[:8], "note": "No archived *Privacy Not Included* review for this brand/product."}


@mcp.tool
def hibp_breaches(domain: str) -> dict:
    """Public data-breach history for a company domain (Have I Been Pwned). Use the brand's main domain, e.g. ring.com."""
    return hibp_breaches_impl(domain)


@mcp.tool
def tosdr(domain_or_name: str) -> dict:
    """Terms of Service; Didn't Read grade (A best .. E worst) and notable clauses for a service, by domain or name."""
    return tosdr_impl(domain_or_name)


@mcp.tool
def pni_archive(brand: str, product: str = "") -> dict:
    """Mozilla's archived *Privacy Not Included* review (sunset Aug 2026) for a brand/product, from the Wayback Machine."""
    return pni_archive_impl(brand, product)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    from starlette.responses import JSONResponse
    return JSONResponse({"ok": True, "tools": ["hibp_breaches", "tosdr", "pni_archive"]})


if __name__ == "__main__":
    # MCP_PORT for local runs; PORT is what Render (and most hosts) inject.
    port = int(os.getenv("MCP_PORT") or os.getenv("PORT") or "8765")
    mcp.run(transport="http", host=os.getenv("MCP_HOST", "0.0.0.0"), port=port)
