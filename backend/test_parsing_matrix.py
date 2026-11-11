"""Model replies and pages in every broken shape: JSON repair and salvage, verdict parsing, policy links, quotes, dates."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from otari import OtariError
from pipeline import (Review, foreign_locale, html_to_text, looks_like_policy, mark_quotes, mostly_latin, parse_json,
                      parse_verdict, pni_stale, privacy_links, privacy_links_text, root_domain, salvage_json, split_tips,
                      title_of)

ROOT = Path(__file__).resolve().parent.parent
EXTRACTION = {
    "data_collected": ["email", "heart rate", "GPS location", 'name "nick"'],
    "sensitive_data": ["health", "location"],
    "sells_data": "no",
    "shares_with": ["Google", "advertisers"],
    "retention": "up to 90 days",
    "red_flags": [{"flag": "Google", "quote": "Fitbit and Google will share"}, {"flag": "Slow delete", "quote": "It may take up to 90 days"}],
    "good_signs": ["export"],
    "nested": {"a": [1, 2, {"b": None}], "c": True},
}
DOC = json.dumps(EXTRACTION)


def is_prefix_of(part, whole) -> bool:
    if isinstance(part, dict):
        return isinstance(whole, dict) and all(k in whole and is_prefix_of(v, whole[k]) for k, v in part.items())
    if isinstance(part, list):
        return isinstance(whole, list) and len(part) <= len(whole) and all(is_prefix_of(a, b) for a, b in zip(part, whole, strict=False))
    return part == whole


@pytest.mark.parametrize("cut", range(1, len(DOC) + 1, 2))
def test_salvage_of_any_truncation_keeps_only_true_fields(cut):
    data = salvage_json("Sure! Here you go:\n" + DOC[:cut])
    assert isinstance(data, dict)
    assert is_prefix_of(data, EXTRACTION)


def test_salvage_of_the_whole_object_is_the_object():
    assert salvage_json(DOC) == EXTRACTION


@pytest.mark.parametrize("raw", ["", "no braces", "]]]", "[1, 2, 3]", "{", '{"a', '{"a":', "\"{}\"", None])
def test_salvage_never_raises(raw):
    assert isinstance(salvage_json(raw), dict)


@pytest.mark.parametrize("raw,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Here: {"a": {"b": 2}} done', {"a": {"b": 2}}),
    ('{"a": "x}y"}', {"a": "x}y"}),
    ("\n\n  {\"k\": [1,2]}  \n", {"k": [1, 2]}),
])
def test_parse_json_accepts_wrapped_objects(raw, expected):
    assert parse_json(raw) == expected


@pytest.mark.parametrize("raw", ["", "nothing", "[1]", "{bad}", "{'single': 1}", '{"a": 1,}', None])
def test_parse_json_rejects_non_objects(raw):
    with pytest.raises(ValueError):
        parse_json(raw)


def reply(text):
    return {"choices": [{"message": {"content": text}}], "usage": {"cost_usd": 0.001}}


GOOD, BAD = '{"sells_data": "no"}', '{"sells_data": "no", "red_flags": [{"flag": "x"'


@pytest.mark.parametrize("first,second,expect_partial,calls", [
    (GOOD, None, False, 1),
    (BAD, GOOD, False, 2),
    (BAD, "nope", True, 2),
    (BAD, OtariError(504, "gateway_timeout", "slow"), True, 2),
    (BAD, OtariError(429, "rate_limited", "slow down"), True, 2),
    ("total garbage", "more garbage", True, 2),
    ("```json\n" + GOOD + "\n```", None, False, 1),
])
def test_json_call_repairs_then_salvages(first, second, expect_partial, calls):
    review = Review("https://x.test/p", None, None, "unit")
    effects = [(reply(first), {})] + ([second if isinstance(second, Exception) else (reply(second), {})] if second is not None else [])
    review.o.chat = AsyncMock(side_effect=effects)
    data, resp, _ = asyncio.run(review.json_call("m", "s", "u", json_mode=True))
    assert review.o.chat.await_count == calls
    assert bool(data.get("partial")) is expect_partial
    if not expect_partial:
        assert data["sells_data"] == "no"


@pytest.mark.parametrize("code", ["budget_exceeded", "user_blocked", "insufficient_funds", "pricing_required"])
def test_json_call_does_not_swallow_budget_errors_in_the_repair_round(code):
    review = Review("https://x.test/p", None, None, "unit")
    review.o.chat = AsyncMock(side_effect=[(reply(BAD), {}), OtariError(403, code, "out")])
    with pytest.raises(OtariError):
        asyncio.run(review.json_call("m", "s", "u"))


VERDICTS = [
    ("SCORE: 4\nLABEL: Very creepy\nHEADLINE: H\nWARNING: yes\n---\nBody", 4, "Very creepy", True, "Body"),
    ("**SCORE:** 2\n**LABEL:** A little creepy\n**WARNING:** no\n---\nB", 2, "A little creepy", False, "B"),
    ("**SCORE:** 5\n**LABEL:** Super creepy\n**HEADLINE:** Eek\n**WARNING:** yes\n---\nB", 5, "Super creepy", True, "B"),
    ("SCORE: 9\n---\nx", 5, None, False, "x"),
    ("SCORE: 0\n---\nx", 1, None, False, "x"),
    ("SCORE: 4/5\n---\nx", 4, None, False, "x"),
    ("SCORE: five\n---\nx", 3, None, False, "x"),
    ("no header at all", 3, None, False, "no header at all"),
    ("score: 3\nwarning: Yes\n---\nlower", 3, None, True, "lower"),
    ("  SCORE :  5\n---\nspaced", 5, None, False, "spaced"),
    ("", 3, None, False, ""),
]


@pytest.mark.parametrize("text,score,label,warning,body", VERDICTS)
def test_parse_verdict_shapes(text, score, label, warning, body):
    v = parse_verdict(text)
    assert v["score"] == score
    assert v["label"] == (label or ["", "Not creepy", "A little creepy", "Somewhat creepy", "Very creepy", "Super creepy"][score])
    assert v["warning_label"] is warning
    assert v["verdict_md"] == body


TIP_HEADINGS = ["Tips to protect yourself:", "**Tips to protect yourself:**", "## Tips to protect yourself", "_Tips to protect yourself_:",
                "TIPS TO PROTECT YOURSELF", "### **Tips to protect yourself:**"]
BULLETS = ["- one", "* one", "• one", "1. one", "2) one", "  - one"]


@pytest.mark.parametrize("heading", TIP_HEADINGS)
@pytest.mark.parametrize("bullet", BULLETS)
def test_tips_split_for_every_heading_and_bullet(heading, bullet):
    body, tips = split_tips(f"Verdict text.\n\n{heading}\n{bullet}\n{bullet.replace('one', '**two**')}\nnot a bullet")
    assert body == "Verdict text."
    assert tips == ["one", "two"]


@pytest.mark.parametrize("body", ["Tips are good: wear a hat.", "Some tips to protect yourself include X.", "No heading here."])
def test_inline_mentions_are_not_a_tips_heading(body):
    assert split_tips(body) == (body, [])


HOSTILE = (ROOT / "hostile" / "index.html").read_text()
HOSTILE_MD = "# SnoopCam Doorbell Pro\n\nBuy now\n\n[Privacy Policy](privacy.html) · [Terms](#)\n"


@pytest.mark.parametrize("base", ["https://creeping-hunger.onrender.com/hostile/", "http://127.0.0.1:8787/hostile/",
                                  "https://creeping-hunger.onrender.com/hostile/index.html"])
def test_hostile_page_policy_link_from_html_and_from_fetched_markdown(base):
    want = base.rsplit("/", 1)[0] + "/privacy.html"
    assert privacy_links(HOSTILE, base) == [want]
    assert privacy_links_text(HOSTILE_MD, base) == [want]


@pytest.mark.parametrize("html,expected", [
    ('<a href="/privacy">x</a>', ["https://shop.test/privacy"]),
    ("<a href='/legal/Privacy-Notice'>x</a>", ["https://shop.test/legal/Privacy-Notice"]),
    ('<a class="f" href="/legal">Privacy &amp; Cookies</a>', ["https://shop.test/legal"]),
    ('<a href="/p"><span>Your <b>Privacy</b> Choices</span></a>', ["https://shop.test/p"]),
    ('<a href="https://other.test/privacy">x</a>', ["https://other.test/privacy"]),
    ('<a href="/privacy">a</a><a href="/privacy">b</a>', ["https://shop.test/privacy"]),
    ('<a href="mailto:privacy@shop.test">mail</a>', []),
    ('<a href="javascript:privacy()">x</a>', []),
    ('<a href="/terms">Terms</a>', []),
    ('<A HREF="/PRIVACY">x</A>', ["https://shop.test/PRIVACY"]),
    ('<a\nhref="/privacy"\n>multi\nline</a>', ["https://shop.test/privacy"]),
    ("", []),
])
def test_privacy_links_in_html(html, expected):
    assert privacy_links(html, "https://shop.test/products/x") == expected


@pytest.mark.parametrize("text,expected", [
    ("[Privacy](/privacy)", ["https://shop.test/privacy"]),
    ("[Your privacy choices](/choices)", ["https://shop.test/choices"]),
    ("See https://shop.test/privacy-policy for more.", ["https://shop.test/privacy-policy"]),
    ("(https://shop.test/privacy)", ["https://shop.test/privacy"]),
    ("[Terms](/terms) and [Help](/help)", []),
    ("[Privacy](mailto:p@shop.test)", []),
    ("[Privacy](/privacy) [privacy again](/privacy)", ["https://shop.test/privacy"]),
    ("plain words about privacy without links", []),
])
def test_privacy_links_in_markdown(text, expected):
    assert privacy_links_text(text, "https://shop.test/products/x") == expected


@pytest.mark.parametrize("url,foreign", [
    ("https://www.fitbit.com/cn/legal/privacy", True), ("https://x.com/zh-cn/privacy", True), ("https://x.com/de/privacy", True),
    ("https://x.com/ja/privacy", True), ("https://x.com/fr-fr/privacy", True), ("https://x.com/legal/privacy/de", True),
    ("https://x.com/global/us/legal/privacy", False), ("https://x.com/en-us/privacy", False), ("https://x.com/en/privacy", False),
    ("https://x.com/privacy", False), ("https://x.com/design/privacy", False), ("https://x.com/news/privacy", False),
    ("https://x.com/deals", False), ("https://x.com/it", True), ("https://x.com/FR/privacy", True),
])
def test_foreign_locale(url, foreign):
    assert foreign_locale(url) is foreign


@pytest.mark.parametrize("text,latin", [
    ("Personal information " * 100, True), ("隐私" * 100, False), ("Политика " * 100, False), ("Café résumé naïve " * 50, True),
    ("", True), ("A" * 100 + "隐" * 10, True), ("ab" + "隐" * 10, False),
])
def test_mostly_latin(text, latin):
    assert mostly_latin(text) is latin


@pytest.mark.parametrize("text,ok", [
    ("We collect personal information. " * 30, True), ("We collect personal data. " * 33, True),
    ("Products Store Help " * 60, False), ("personal information", False), ("隐私政策隐私政策 personal data " * 200, False),
    ("PERSONAL DATA we hold. " * 40, True),
])
def test_looks_like_policy(text, ok):
    assert looks_like_policy(text) is ok


@pytest.mark.parametrize("host,root", [
    ("www.fitbit.com", "fitbit.com"), ("fitbit.com", "fitbit.com"), ("shop.bbc.co.uk", "bbc.co.uk"), ("a.b.c.example.org", "example.org"),
    ("https://www.ring.com/en/x", "ring.com"), ("localhost", "localhost"), ("127.0.0.1", "0.1"), ("x.com.au", "x.com.au"),
    ("store.google.com:443", "google.com"), ("WWW.AMAZON.COM", "amazon.com"),
])
def test_root_domain(host, root):
    assert root_domain(host) == root


@pytest.mark.parametrize("html,text", [
    ("<p>a</p><p>b</p>", "a\nb"), ("<p>a</p>\n\n<p>b</p>", "a\n\nb"), ("<script>evil()</script>ok", "ok"), ("<style>x{}</style>ok", "ok"),
    ("a<br>b", "a\nb"), ("&amp; &lt;b&gt;", "& <b>"), ("<div>  lots   of   space </div>", "lots of space"),
    ("<noscript>n</noscript><svg><text>s</text></svg>t", "t"), ("<template><p>hid</p></template>v", "v"),
])
def test_html_to_text(html, text):
    assert html_to_text(html) == text


@pytest.mark.parametrize("html,title", [
    ("<title>A &amp; B</title>", "A & B"), ("<TITLE>\n x \n</TITLE>", "x"), ("<title lang=en>T</title>", "T"), ("none", ""),
])
def test_title_of(html, title):
    assert title_of(html) == title


POLICY = "“It may take up to 90 days to delete all of your information,” like the data in **backup** systems.\nFitbit and Google will share"


@pytest.mark.parametrize("quote,verified", [
    ("It may take up to 90 days to delete all of your information", True), ("it MAY take up to 90 days", True),
    ("like the data in backup systems", True), ("Fitbit and Google will share", True), ("delete all of your\ninformation", True),
    ("It may take up to 30 days", False), ("Google sells your data", False), ("90 days to erase", False),
])
def test_quotes_are_checked_word_for_word(quote, verified):
    ex = {"red_flags": [{"flag": "f", "quote": quote}]}
    mark_quotes(ex, POLICY)
    assert ex["red_flags"][0]["quote_verified"] is verified


@pytest.mark.parametrize("flags", [None, [], ["plain string flag"], [{"flag": "no quote"}], [{"quote": ""}], [{"quote": 5}], "oops"])
def test_odd_red_flags_are_left_alone(flags):
    ex = {"red_flags": flags}
    mark_quotes(ex, POLICY)
    for f in ex["red_flags"] or []:
        assert not (isinstance(f, dict) and "quote_verified" in f)


@pytest.mark.parametrize("date,stale", [
    ("Sept. 21, 2023", True), ("Nov 8, 2023", True), ("November 8, 2023", True), ("Jan. 3, 2022", True),
    ("garbage", True), ("", True), ("2023-01-01", True),
])
def test_old_or_unreadable_pni_dates_are_stale(date, stale):
    assert pni_stale({"pni_found": True, "pni_review_date": date}) is stale


def test_recent_pni_date_is_not_stale():
    from datetime import datetime, timedelta
    recent = (datetime.now() - timedelta(days=30)).strftime("%B %d, %Y")
    assert pni_stale({"pni_found": True, "pni_review_date": recent}) is False


@pytest.mark.parametrize("research", [{}, {"pni_found": False, "pni_review_date": "Nov 8, 2023"}, {"pni_found": None}])
def test_no_archived_review_is_neither_stale_nor_fresh(research):
    assert pni_stale(research) is None
