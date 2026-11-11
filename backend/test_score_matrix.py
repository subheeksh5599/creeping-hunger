"""The sandbox score script, checked against an independent restatement of its six rules."""
from __future__ import annotations

import contextlib
import io
import itertools
import json

import pytest

from pipeline import compute_code

PLAIN = "We keep your data safe and do not sell it to anyone at all. "
MAY = "We may keep your data for a short time only. "
DENSE = ("Notwithstanding contractual obligations, organizational representatives systematically "
         "communicate individualized information electronically, administratively, and internationally. ")


def run(policy: str, facts: dict, archived: str = "") -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compute_code(policy, archived, facts), {})
    return json.loads(out.getvalue().strip().splitlines()[-1])


def policy_text(dense: bool, many_may: bool) -> str:
    return (DENSE * 20 if dense else PLAIN * 20) + (MAY * 30 if many_may else MAY * 3)


RETENTION = {"none": ("", 0), "short": ("Deleted within 30 days.", 0), "long": ("Up to 90 days to delete.", 1),
             "forever": ("Kept as long as necessary.", 1)}


def expected(dense, many_may, n_sensitive, retention, pni, breaches, blocked):
    points = int(dense) + int(many_may) + int(n_sensitive >= 2) + RETENTION[retention][1] + int(pni) + int(breaches >= 1)
    return 5 if blocked else min(5, 1 + points)


CASES = list(itertools.product([False, True], [False, True], [0, 1, 2, 3], list(RETENTION), [False, True], [0, 1, 4], [False, True]))


@pytest.mark.parametrize("dense,many_may,n_sensitive,retention,pni,breaches,blocked", CASES)
def test_score_matches_the_published_rules(dense, many_may, n_sensitive, retention, pni, breaches, blocked):
    facts = {"sensitive": ["biometrics", "health", "location"][:n_sensitive], "retention": RETENTION[retention][0],
             "pni_warning": pni, "breaches": breaches, "blocked": blocked}
    stats = run(policy_text(dense, many_may), facts)
    score = stats["score"]
    assert score["value"] == expected(dense, many_may, n_sensitive, retention, pni, breaches, blocked)
    shown = sum(f["point"] for f in score["factors"] if f["point"] in (0, 1))
    assert score["value"] == (5 if blocked else min(5, 1 + shown))
    assert (score["factors"][-1]["name"] == "Prompt injection on the page") is blocked


@pytest.mark.parametrize("text,days,forever", [
    ("", 0, False),
    ("We delete data within 30 days.", 30, False),
    ("Deletion may take up to 90 days.", 90, False),
    ("We keep logs for 18 months.", 540, False),
    ("Backups are kept for 2 years.", 730, False),
    ("Records are kept 1 year.", 365, False),
    ("Data is removed after 6 weeks.", 42, False),
    ("Within 7 days, or 13 months for backups.", 390, False),
    ("We retain data as long as necessary.", 0, True),
    ("Retained indefinitely.", 0, True),
    ("Kept until you delete your account.", 0, True),
    ("Deleted when no longer needed.", 0, True),
    ("Deleted when no longer necessary.", 0, True),
    ("Some data cannot be deleted.", 0, True),
    ("We keep it for 24 hours.", 0, False),
    ("Kept for two years.", 730, False),
    ("Kept for three months.", 90, False),
    ("We store recordings permanently.", 0, True),
    ("Kept for 1 day.", 1, False),
    ("Kept for ninety days.", 90, False),
    ("A six-month retention window.", 180, False),
    ("Kept for nine days.", 9, False),
    ("Kept for 31 days.", 31, False),
    ("Up to 4 weeks, then 12 months in backup, or as long as needed.", 360, True),
])
def test_retention_reading(text, days, forever):
    row = next(f for f in run(PLAIN * 5, {"retention": text})["score"]["factors"] if f["name"] == "Deletion time")
    assert row["point"] == int(days > 30 or forever)
    if days:
        assert f"up to {days} days" in row["value"]
    assert ("kept indefinitely" in row["value"]) is forever
    if not days and not forever:
        assert row["value"] == "not stated"


@pytest.mark.parametrize("word,pattern_key,count", [
    ("We sell data.", "sell", 1), ("We are selling it.", "sell", 1), ("No sale of personal data.", "sell", 1),
    ("We do not share.", "share", 1), ("Shared and sharing.", "share", 2), ("Third-party and third parties.", "third_party", 2),
    ("Advertising and advertisers.", "advertis", 2), ("Our partners and affiliates.", "partners_affiliates", 2),
    ("Law enforcement or police.", "law_enforcement", 2), ("Upon a subpoena.", "law_enforcement", 1),
    ("To train our models.", "ai_training", 1), ("Machine learning helps.", "ai_training", 1),
    ("Location and GPS.", "location", 2), ("Biometric facial data.", "biometric", 2),
    ("Audio and video recordings.", "audio_video", 3), ("Children under 13.", "children", 2),
    ("We retain it.", "retain", 1), ("As long as needed.", "retain", 1), ("You may. We may. They may.", "may", 3),
    ("Mayor Maybe.", "may", 0), ("Nothing here.", "sell", 0), ("Resellers.", "sell", 0),
])
def test_clause_counts(word, pattern_key, count):
    key = {"advertis": "advertising"}.get(pattern_key, pattern_key)
    assert run(word, {})["clause_counts"][key] == count


@pytest.mark.parametrize("old,new,added,removed,kept", [
    (PLAIN, PLAIN, 0, 0, 1.0),
    (PLAIN, PLAIN + "We now share recordings with partners for advertising. ", 1, 0, 1.0),
    (PLAIN + "We never share recordings with any partners at all. ", PLAIN, 0, 1, 0.5),
    ("Old sentence number one is long enough. Old sentence number two is long enough. ",
     "Brand new sentence alpha is long enough. Brand new sentence beta is long enough. ", 2, 2, 0.0),
    ("Short. Tiny.", PLAIN, 1, 0, 0.0),
])
def test_diff_against_archive(old, new, added, removed, kept):
    diff = run(new, {}, archived=old)["diff_vs_archive"]
    assert (diff["added_sentences"], diff["removed_sentences"], diff["kept_share"]) == (added, removed, kept)
    assert 0 <= diff["similarity"] <= 1


@pytest.mark.parametrize("old", ["", "   ", "\n\n"])
def test_no_archive_means_no_diff(old):
    assert run(PLAIN, {}, archived=old)["diff_vs_archive"] is None


def test_new_risky_sentences_are_listed_and_capped():
    added = "".join(f"Clause {i}: we share your data with partner number {i} today. " for i in range(9))
    diff = run(PLAIN + added, {}, archived=PLAIN)["diff_vs_archive"]
    assert len(diff["new_risky_sentences"]) == 5
    assert all("share" in s for s in diff["new_risky_sentences"])


@pytest.mark.parametrize("dense", [False, True])
def test_reading_grade_tracks_word_length(dense):
    stats = run(DENSE * 10 if dense else PLAIN * 10, {})
    assert (stats["fk_grade"] >= 13) is dense
    assert stats["reading_minutes"] == round(stats["words"] / 238, 1)


@pytest.mark.parametrize("payload", ['"""', "'''", "\\", "}{", "\x00", "ü" * 50, "__PAYLOAD__", "print('x')"])
def test_policy_text_cannot_break_out_of_the_script(payload):
    stats = run(PLAIN + payload, {"retention": payload})
    assert stats["words"] > 0 and "score" in stats
