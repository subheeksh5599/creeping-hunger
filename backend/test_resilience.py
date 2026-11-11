"""Gateway errors stay short; a failed research step still finishes the review."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from otari import OtariError, _raise
from pipeline import Review

HTML_504 = (
    b"<!DOCTYPE html><html><head><title>504 Gateway Time-out</title></head>"
    b"<body>nginx</body></html>"
)


class HtmlErrorTest(unittest.TestCase):
    def test_html_body_is_short(self):
        r = httpx.Response(504, headers={"content-type": "text/html"}, content=HTML_504)
        with self.assertRaises(OtariError) as cm:
            _raise(r)
        err = cm.exception
        self.assertEqual(err.status, 504)
        self.assertEqual(err.friendly, "504 Otari gateway error")
        self.assertEqual(err.detail, "Otari gateway error")
        self.assertNotIn("<html", err.friendly)
        self.assertNotIn("<!DOCTYPE", str(err))


class ResearchDegradedTest(unittest.TestCase):
    def test_research_timeout_still_done(self):
        events = asyncio.run(self._run(OtariError(504, "gateway_error", "Otari gateway error")))
        types = [e["type"] for e in events]
        self.assertIn("done", types)
        self.assertNotIn("error", types)
        research = [e for e in events if e.get("id") == "research" and e.get("status") == "done"]
        self.assertTrue(research)
        self.assertIn("Research unavailable", research[0]["title"])
        done = next(e for e in events if e["type"] == "done")
        self.assertTrue(any("Research unavailable" in n for n in done.get("notes") or []))

    def test_budget_exceeded_still_surfaces(self):
        events = asyncio.run(self._run(OtariError(403, "budget_exceeded", "out")))
        types = [e["type"] for e in events]
        self.assertIn("error", types)
        self.assertNotIn("done", types)
        self.assertEqual(next(e for e in events if e["type"] == "error")["code"], "budget_exceeded")

    @staticmethod
    async def _run(research_error: OtariError):
        review = Review(
            "https://example.com/product",
            "Example Product collects personal information and privacy data.",
            None,
            "unit-test",
        )
        review._tool_availability = AsyncMock(return_value={"search": False, "fetch": False, "code": False})
        review.read_url = AsyncMock(return_value=("short", "", "local_fetch"))
        review.json_call = AsyncMock(side_effect=[
            ({"brand": "Ex", "product": "Thing", "category": "gadget", "brand_domain": "example.com"}, {}, {}),
            ({"data_collected": ["email"], "red_flags": []}, {}, {}),
        ])
        review._research = AsyncMock(side_effect=research_error)
        review._compute = AsyncMock(return_value=({"words": 10}, 0.0))
        review._archived_policy = AsyncMock(return_value=("", None))

        async def fake_judge(*_a, **_k):
            yield {"type": "step", "id": "judge", "status": "done", "title": "Verdict written"}
            yield {"type": "result", "score": 3, "label": "Somewhat creepy", "headline": "n",
                   "warning_label": False, "verdict_md": "x", "brand": "Ex", "product": "Thing",
                   "policy_url": None, "extraction": {}, "research": {}, "stats": {}, "blocked": False}

        review._judge = fake_judge
        events = []
        with patch("pipeline.guard.validate", new=AsyncMock(return_value={
            "valid": True, "cost_usd": 0, "explanation": "", "score": 0,
        })):
            with patch("pipeline.store.save"), patch("pipeline.store.latest_for", return_value=None), \
                    patch.object(review.o, "end_user_budget", new=AsyncMock(return_value=None)):
                async for e in review.run():
                    events.append(e)
        return events


if __name__ == "__main__":
    unittest.main()
