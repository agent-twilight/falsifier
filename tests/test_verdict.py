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
