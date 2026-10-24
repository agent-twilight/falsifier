"""A thread per plan, and the dot that makes this not a chat app.

The distinguishing behaviour is narrow and worth pinning down: the agent
can add to a thread without being asked, and that thread is then visibly
waiting. Everything else here is ordinary.
"""

from __future__ import annotations

import pytest

from falsifier.memory import db, sessions


@pytest.fixture()
def conn(tmp_path):
    connection = db.init_db(tmp_path / "t.db")
    yield connection
    connection.close()


def test_a_plan_gets_a_thread(conn):
    sid = sessions.create(conn, "Preparing for JEE in April")
    sessions.add(conn, sid, "user", "I am preparing for JEE in April.")
    session = sessions.get(conn, sid, "personal")
    assert session.title == "Preparing for JEE in April"
    assert len(sessions.history(conn, sid)) == 1


def test_an_answer_does_not_mark_the_thread_unread(conn):
    """Replying to you is not news. Only unprompted speech is."""
    sid = sessions.create(conn, "x")
    sessions.add(conn, sid, "user", "a question")
    sessions.add(conn, sid, "agent", "an answer", kind="text")
    sessions.add(conn, sid, "agent", "a finding", kind="finding")
    assert sessions.get(conn, sid, "personal").unread == 0


def test_an_unprompted_message_lights_the_thread(conn):
    """The whole product, in one flag."""
    sid = sessions.create(conn, "x")
    sessions.add(conn, sid, "agent", "the date moved", kind="alert")
    session = sessions.get(conn, sid, "personal")
    assert session.unread == 1
    assert session.has_news


def test_several_alerts_accumulate(conn):
    sid = sessions.create(conn, "x")
    for _ in range(3):
        sessions.add(conn, sid, "agent", "something changed", kind="alert")
    assert sessions.get(conn, sid, "personal").unread == 3


def test_opening_a_thread_clears_the_dot(conn):
    sid = sessions.create(conn, "x")
    sessions.add(conn, sid, "agent", "news", kind="alert")
    sessions.mark_read(conn, sid)
    assert not sessions.get(conn, sid, "personal").has_news


def test_an_alert_knows_it_was_unprompted(conn):
    sid = sessions.create(conn, "x")
    sessions.add(conn, sid, "agent", "news", kind="alert")
    sessions.add(conn, sid, "agent", "reply", kind="text")
    messages = sessions.history(conn, sid)
    assert messages[0].unprompted is True
    assert messages[1].unprompted is False


def test_the_panel_puts_pinned_first_then_most_recent(conn):
    old = sessions.create(conn, "older")
    new = sessions.create(conn, "newer")
    sessions.add(conn, new, "user", "hello")
    sessions.set_pinned(conn, old, True)
    assert [s.id for s in sessions.listing(conn)][0] == old


def test_demo_threads_and_personal_threads_never_mix(conn):
    personal = sessions.create(conn, "mine", mode="personal")
    demo = sessions.create(conn, "public", mode="demo")
    assert [s.id for s in sessions.listing(conn, "personal")] == [personal]
    assert [s.id for s in sessions.listing(conn, "demo")] == [demo]
    assert sessions.get(conn, personal, "demo") is None, "not reachable by id"


def test_a_thread_can_be_found_from_its_claim(conn):
    """The watch needs to know where to speak."""
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.commit()
    sid = sessions.create(conn, "t", claim_id=1)
    assert sessions.for_claim(conn, 1) == sid


def test_deleting_a_claim_leaves_the_conversation_intact(conn):
    conn.execute("INSERT INTO claims (id, text) VALUES (1, 'a claim')")
    conn.commit()
    sid = sessions.create(conn, "t", claim_id=1)
    sessions.add(conn, sid, "user", "said something")
    conn.execute("DELETE FROM claims WHERE id = 1")
    conn.commit()
    assert sessions.get(conn, sid, "personal") is not None
    assert len(sessions.history(conn, sid)) == 1


# --- titles ---------------------------------------------------------------


def test_a_title_is_cut_at_a_word_not_mid_word():
    long = "I am preparing for the JEE Main examination in April next year and"
    title = sessions.title_from(long)
    assert len(title) <= 60
    assert not title.rstrip("…").endswith("exami")


def test_a_title_stops_at_the_first_clause():
    assert sessions.title_from(
        "I work at Nvidia. I think I will become rich."
    ) == "I work at Nvidia"


def test_a_short_claim_is_its_own_title():
    assert sessions.title_from("JEE is in April") == "JEE is in April"


def test_an_empty_claim_still_gets_a_label(conn):
    sid = sessions.create(conn, "")
    assert sessions.get(conn, sid, "personal").title == "New plan"
