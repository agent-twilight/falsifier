"""Models wrap JSON in prose and markdown. The parser must cope.

Every input here is a shape a Nemotron reply has actually taken, or an
obvious near-miss worth guarding against.
"""

from __future__ import annotations

import pytest

from falsifier.pipeline import parsing


def test_plain_json_array():
    assert parsing.extract_json('["a", "b"]') == ["a", "b"]


def test_fenced_json():
    reply = 'Here you go:\n```json\n["a", "b"]\n```\nHope that helps.'
    assert parsing.extract_json(reply) == ["a", "b"]


def test_fenced_without_language_tag():
    assert parsing.extract_json("```\n[1, 2]\n```") == [1, 2]


def test_json_buried_in_prose():
    reply = 'After thinking it over: [{"assumption": "x"}] — that is my answer.'
    assert parsing.extract_json(reply) == [{"assumption": "x"}]


def test_empty_reply_raises():
    with pytest.raises(parsing.ParseError):
        parsing.extract_json("   ")


def test_no_json_raises_rather_than_returning_nothing():
    with pytest.raises(parsing.ParseError):
        parsing.extract_json("I am not sure how to answer that.")


def test_list_of_dicts_uses_the_named_key():
    value = [{"assumption": "first", "why": "..."}, {"assumption": "second"}]
    assert parsing.as_list_of_strings(value, key="assumption") == ["first", "second"]


def test_falls_back_to_the_first_string_when_key_is_absent():
    value = [{"hypothesis": "the cohort is mostly undergrads"}]
    assert parsing.as_list_of_strings(value, key="missing") == [
        "the cohort is mostly undergrads"
    ]


def test_dict_wrapping_a_list_is_unwrapped():
    """Models often answer {"assumptions": [...]} despite being asked for a list."""
    value = {"assumptions": ["a", "b"]}
    assert parsing.as_list_of_strings(value) == ["a", "b"]


def test_blank_and_whitespace_entries_are_dropped():
    assert parsing.as_list_of_strings(["a", "", "   ", "b"]) == ["a", "b"]


def test_non_list_raises():
    with pytest.raises(parsing.ParseError):
        parsing.as_list_of_strings("just a string")
