"""The verdict must be able to agree, disagree, or admit it cannot tell.

No network: the model call is replaced with a canned reply, so these test
the logic around the model rather than the model itself.
"""

from __future__ import annotations

import pytest

from falsifier.pipeline import parsing, read, verdict

EVIDENCE = [
    read.Evidence(
        quote="60% of the entering class enrolled directly from undergraduate study.",
        url="https://cs.stanford.edu/admissions/profile",
        title="Class profile",
        source_tier="primary",
        bearing="SUPPORTS",
        published_date="2026-09-01",
    )
]


def canned(monkeypatch, payload):
    monkeypatch.setattr(parsing, "complete_json", lambda *a, **k: payload)


def test_it_can_agree_with_the_user(monkeypatch):
    """Agreeing is a result, not a failure to find something."""
    canned(monkeypatch, {
        "verdict": "SUPPORTS", "statement": "The claim held up.",
        "evidence_index": 1, "confidence": 0.8,
    })
    v = verdict.judge("c", "s", EVIDENCE)
    assert v.stance == verdict.SUPPORTED
    assert v.agrees
    assert v.evidence.url.startswith("https://cs.stanford.edu")


def test_it_can_challenge(monkeypatch):
    canned(monkeypatch, {
        "verdict": "CHALLENGES", "statement": "Most admits come straight from undergrad.",
        "evidence_index": 1, "confidence": 0.9,
    })
    v = verdict.judge("c", "s", EVIDENCE)
    assert v.stance == verdict.CHALLENGED
    assert v.evidence is not None


def test_it_can_say_it_cannot_tell(monkeypatch):
    canned(monkeypatch, {
        "verdict": "UNVERIFIABLE", "statement": "Cannot be settled.",
        "evidence_index": None,
        "reason": "Stanford does not publish work-experience statistics.",
    })
    v = verdict.judge("c", "s", [])
    assert v.stance == verdict.UNVERIFIABLE
    assert "does not publish" in v.reason
    assert v.evidence is None


def test_a_conclusion_without_a_quote_is_downgraded(monkeypatch):
    """Rule 1 in code: take a side only if you can point at a real line."""
    canned(monkeypatch, {
        "verdict": "CHALLENGES", "statement": "I reckon this is wrong.",
        "evidence_index": None, "confidence": 0.9,
    })
    v = verdict.judge("c", "s", EVIDENCE)
    assert v.stance == verdict.UNVERIFIABLE
    assert "without citing" in v.reason


def test_an_out_of_range_evidence_index_is_not_trusted(monkeypatch):
    canned(monkeypatch, {
        "verdict": "SUPPORTS", "statement": "Backed up.", "evidence_index": 7,
    })
    v = verdict.judge("c", "s", EVIDENCE)
    assert v.stance == verdict.UNVERIFIABLE


def test_unknown_verdict_defaults_to_unverifiable(monkeypatch):
    canned(monkeypatch, {"verdict": "PROBABLY FINE", "statement": "x"})
    assert verdict.judge("c", "s", EVIDENCE).stance == verdict.UNVERIFIABLE


def test_unverifiable_always_carries_a_reason(monkeypatch):
    canned(monkeypatch, {"verdict": "UNVERIFIABLE", "statement": "x"})
    v = verdict.judge("c", "s", [])
    assert v.reason, "an unverifiable verdict with no reason is useless"


def test_confidence_is_clamped(monkeypatch):
    canned(monkeypatch, {
        "verdict": "SUPPORTS", "statement": "x", "evidence_index": 1,
        "confidence": 4.2,
    })
    assert verdict.judge("c", "s", EVIDENCE).confidence == 1.0


def test_report_headline_when_the_claim_holds():
    report = verdict.ClaimReport("c", [
        verdict.Verdict(verdict.SUPPORTED, "held", EVIDENCE[0], confidence=0.8)
    ])
    assert "could not" in report.headline.lower()
    assert report.supported and not report.challenged


def test_report_headline_when_objections_survive():
    report = verdict.ClaimReport("c", [
        verdict.Verdict(verdict.CHALLENGED, "a", EVIDENCE[0]),
        verdict.Verdict(verdict.CHALLENGED, "b", EVIDENCE[0]),
    ])
    assert "2 objections survived" in report.headline


def test_ambiguities_are_passed_to_the_model(monkeypatch):
    seen = {}

    def spy(tier, prompt, **kwargs):
        seen["prompt"] = prompt
        return {"verdict": "UNVERIFIABLE", "statement": "x", "reason": "y"}

    monkeypatch.setattr(parsing, "complete_json", spy)
    verdict.judge("c", "s", [], ambiguities=["which programme?"])
    assert "which programme?" in seen["prompt"]
    assert "HAS NOT SPECIFIED" in seen["prompt"]


def test_a_verdict_wrapped_in_a_list_is_unwrapped(monkeypatch):
    """Seen live: losing a whole sub-claim over JSON shape is not acceptable."""
    canned(monkeypatch, [{"verdict": "SUPPORTS", "statement": "held",
                          "evidence_index": 1}])
    assert verdict.judge("c", "s", EVIDENCE).stance == verdict.SUPPORTED


def test_a_verdict_in_a_single_key_envelope_is_unwrapped(monkeypatch):
    canned(monkeypatch, {"result": {"verdict": "CHALLENGES", "statement": "x",
                                    "evidence_index": 1}})
    assert verdict.judge("c", "s", EVIDENCE).stance == verdict.CHALLENGED


# ---------------------------------------------------------------------------
# A verdict can be no stronger than the source under it. A Reddit post was
# allowed to carry an objection at 80% confidence on 19 Oct.
# ---------------------------------------------------------------------------


def _evidence(tier, url="https://example.com/x"):
    return [read.Evidence(quote="some real line", url=url, title="t",
                          source_tier=tier, bearing="SUPPORTS",
                          published_date=None)]


def test_a_weak_source_is_capped_but_may_still_speak(monkeypatch):
    """Loosened 25 Oct: refusing outright was worse than saying so quietly.

    A forum post can support a finding, but only at low confidence, and
    the reader can see the tier it rests on.
    """
    canned(monkeypatch, {"verdict": "CHALLENGES", "statement": "x",
                         "evidence_index": 1, "confidence": 0.8})
    v = verdict.judge("c", "s", _evidence("weak", "https://reddit.com/r/Python/x"))
    assert v.stance == verdict.CHALLENGED
    assert v.confidence == 0.5, "capped to what a forum post can bear"


def test_evidence_too_weak_to_act_on_is_still_refused(monkeypatch):
    """The floor still exists; it is just lower than the weak ceiling now."""
    canned(monkeypatch, {"verdict": "CHALLENGES", "statement": "x",
                         "evidence_index": 1, "confidence": 0.1})
    v = verdict.judge("c", "s", _evidence("weak", "https://forum.example/x"))
    assert v.stance == verdict.UNVERIFIABLE
    assert "weak source" in v.reason


def test_a_secondary_source_is_capped_but_still_counts(monkeypatch):
    canned(monkeypatch, {"verdict": "CHALLENGES", "statement": "x",
                         "evidence_index": 1, "confidence": 0.95})
    v = verdict.judge("c", "s", _evidence("secondary"))
    assert v.stance == verdict.CHALLENGED
    assert v.confidence == 0.75, "capped to what a secondary source can bear"


def test_a_primary_source_keeps_full_confidence(monkeypatch):
    canned(monkeypatch, {"verdict": "SUPPORTS", "statement": "x",
                         "evidence_index": 1, "confidence": 0.95})
    v = verdict.judge("c", "s", _evidence("primary", "https://stanford.edu/x"))
    assert v.stance == verdict.SUPPORTED
    assert v.confidence == 0.95


def test_criteria_are_put_to_the_model_as_all_or_nothing(monkeypatch):
    """A near-miss on wording must not pass as a counter-example."""
    seen = {}

    def spy(tier, prompt, **kwargs):
        seen["prompt"] = prompt
        return {"verdict": "UNVERIFIABLE", "statement": "x", "reason": "y"}

    monkeypatch.setattr(parsing, "complete_json", spy)
    verdict.judge("c", "s", [], criteria=[
        "monitors sources outside the user's control",
        "alerts without being asked",
    ])
    assert "MUST SATISFY EVERY ONE" in seen["prompt"]
    assert "outside the user's control" in seen["prompt"]
    assert "adjacent" in seen["prompt"]
