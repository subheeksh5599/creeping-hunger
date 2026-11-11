"""Tips are split out of the verdict; a repeat review of the same URL replays the saved one."""
from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from pipeline import Review, foreign_locale, looks_like_policy, mostly_latin, parse_verdict

VERDICT = """SCORE: 4
LABEL: Very creepy
HEADLINE: It counts your steps and your secrets
WARNING: yes
---
They collect heart rate and location.

**Tips to protect yourself:**
* Turn off location history
- Use a private email
1. Delete old data
"""

SAVED = {
    "summary": {"id": "ch-old", "created_at": time.time() - 60},
    "events": [
        {"type": "start", "review_id": "ch-old", "url": "https://x.test/p", "models": {}},
        {"type": "step", "id": "read", "status": "done", "title": "Read", "total_cost_usd": 0},
        {"type": "result", "score": 4, "label": "Very creepy", "verdict_md": "v", "tips": []},
        {"type": "done", "review_id": "ch-old", "total_cost_usd": 0.004, "seconds": 80.0, "notes": []},
    ],
}


class TipsTest(unittest.TestCase):
    def test_tips_split_from_verdict(self):
        v = parse_verdict(VERDICT)
        self.assertEqual(v["score"], 4)
        self.assertTrue(v["warning_label"])
        self.assertEqual(v["tips"], ["Turn off location history", "Use a private email", "Delete old data"])
        self.assertNotIn("Tips to protect", v["verdict_md"])
        self.assertIn("heart rate", v["verdict_md"])

    def test_no_tips_keeps_body(self):
        v = parse_verdict("SCORE: 2\n---\nFine.")
        self.assertEqual((v["verdict_md"], v["tips"]), ("Fine.", []))


class PolicyPickTest(unittest.TestCase):
    def test_foreign_locale_policies_go_last(self):
        urls = ["https://www.fitbit.com/cn/legal/privacy-policy", "https://www.fitbit.com/global/us/legal/privacy-policy"]
        self.assertEqual(sorted(urls, key=foreign_locale)[0], urls[1])

    def test_non_latin_policy_is_skipped(self):
        self.assertFalse(mostly_latin("隐私政策" * 200))
        self.assertTrue(mostly_latin("We collect your personal information. " * 50))

    def test_nav_shell_is_not_a_policy(self):
        self.assertFalse(looks_like_policy("Fitbit Legal - Privacy Policy\n- Products\n- Store\n" * 30))
        self.assertTrue(looks_like_policy("We collect your personal information and share it. " * 30))


class CacheTest(unittest.TestCase):
    def run_review(self, **kw):
        review = Review("https://x.test/p", None, None, "unit", **kw)

        async def live():
            yield {"type": "live"}
        review._run = live

        async def go():
            with patch("pipeline.store.latest_for", return_value=SAVED), patch("pipeline.store.save"), \
                    patch.object(review.o, "end_user_budget", new=AsyncMock(return_value={"spend_usd": 0.01})):
                return [e async for e in review.run()]
        return asyncio.run(go())

    def test_repeat_review_replays_saved_events(self):
        events = self.run_review()
        self.assertEqual([e["type"] for e in events], ["start", "step", "result", "done"])
        self.assertEqual(events[0]["cached_from"], "ch-old")
        done = events[-1]
        self.assertTrue(done["cached"])
        self.assertEqual(done["original_seconds"], 80.0)
        self.assertLess(done["seconds"], 5)
        self.assertEqual(done["budget"], {"spend_usd": 0.01})

    def test_fresh_and_forced_fallback_skip_cache(self):
        for kw in ({"fresh": True}, {"force_fallback": True}):
            self.assertEqual([e["type"] for e in self.run_review(**kw)], ["live"])


if __name__ == "__main__":
    unittest.main()
