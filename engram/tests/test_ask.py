"""Answering from the brain with scripted models: the relevance filter, citations, and the support check."""
import math
from datetime import UTC, datetime

import pytest

from engram.ask import ask
from engram.db import connect
from engram.index import refresh_stats
from engram.judge import Judge
from engram.sources.enron import Message
from engram.store import ingest_messages

pytestmark = pytest.mark.db
OWNER = "vince.kaminski@enron.com"


class ByPrompt:
    model = "scripted"

    def score(self, system, user, keys):
        p = 0.98 if "closes on June 5" in user else 0.02      # only the closing email holds (and supports) it
        return {"yes": math.log(p), "no": math.log(1 - p)}


class FakeLLM:
    def __init__(self):
        self.prompts = []

    def generate_json(self, model, system, user, schema, max_tokens=600):
        self.prompts.append(user)
        return {"answer": "The storage deal closes on June 5.", "cites": [1, 1, 9]}


def test_ask_filters_cites_and_checks_support(db_url):
    def mail(ref, subject, body):
        return Message(ref, "inbox", datetime(2001, 5, 1, tzinfo=UTC), "a@enron.com", (OWNER,), (), subject, body)

    filler = [mail(f"v/inbox/{i}.", f"Lunch {i}", f"Lunch plans number {i} at the usual place.") for i in range(8)]
    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/100.", "Storage deal", "The storage deal closes on June 5."),
                               mail("v/inbox/101.", "Storage pricing", "Storage pricing is attached."), *filler],
                        {OWNER})
        conn.commit()
        refresh_stats(conn)
        closing = conn.execute("SELECT item_id FROM item_refs WHERE ref = 'v/inbox/100.'").fetchone()["item_id"]
        llm = FakeLLM()
        with Judge(db_url, ByPrompt()) as judge:
            r = ask(conn, judge, llm, "m", None, "When does the storage deal close?")
            assert len(r.considered) == 2 and r.kept == (closing,)            # the pricing email is dropped
            assert "[1]" in llm.prompts[0] and "Storage pricing" not in llm.prompts[0]
            assert r.cites == (closing,)                                      # repeated and out-of-range cites go
            assert r.support.settled and r.support.value == "yes"
            none = ask(conn, judge, llm, "m", None, "What did the lunch plans say about pricing?")
            assert none.cites == () and none.support is None and len(llm.prompts) == 1   # no model call


class Sale:
    """Relevance and support: yes only for the email that states the completion date. Grader: yes when the
    response gives that date."""

    model = "scripted-sale"

    def score(self, system, user, keys):
        p = 0.98 if "completes on July 9" in user or "Response: The sale completes on July 9" in user else 0.02
        return {"yes": math.log(p), "no": math.log(1 - p)}


def test_qa_grades_held_out_questions(db_url):
    import random

    from engram.evaluate import qa
    from engram.finetune import split_of
    from engram.sources.enronqa import QA
    from engram.text import thread_key

    subject = next(s for s in (f"Pipeline sale {i}" for i in range(200)) if split_of(f"thread:{thread_key(s)}") ==
                   "test")                                                   # a conversation the judge never saw

    class Answers:
        def generate_json(self, model, system, user, schema, max_tokens=600):
            return {"answer": "The sale completes on July 9.", "cites": [1]}

    with connect(db_url) as conn:
        ingest_messages(conn, [Message("v/inbox/200.", "inbox", datetime(2001, 6, 1, tzinfo=UTC), "b@enron.com",
                                       (OWNER,), (), subject, "The pipeline sale completes on July 9.")], {OWNER})
        conn.commit()
        refresh_stats(conn)
        with Judge(db_url, Sale()) as judge, Judge(db_url, None, Sale()) as grader:
            report, rows = qa(conn, judge, grader, Answers(), "m", None,
                              [QA("q1", "v/inbox/200.", "When does the pipeline sale complete?", "July 9", ()),
                               QA("q2", "v/nowhere/1.", "Not in the brain?", "-", ())], 5, random.Random(0))
    assert report["questions"] == 1 and report["correct"] == 1.0 and report["gold_cited"] == 1.0
    assert report["support_check"]["settled_supported"] == 1.0 and rows[0]["correct"]


class Zebra:
    """The count email is surely relevant; the memo, merely possible."""

    model = "scripted-zebra"

    def score(self, system, user, keys):
        p = 0.98 if "count is 12" in user else 0.6 if "planning memo" in user else 0.02
        return {"yes": math.log(p), "no": math.log(1 - p)}


def test_the_judge_orders_what_the_large_model_reads(db_url):
    def mail(ref, subject, body):
        return Message(ref, "inbox", datetime(2001, 7, 1, tzinfo=UTC), "z@enron.com", (OWNER,), (), subject, body)

    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/300.", "Zebra planning memo", "Zebra zebra zebra: the planning memo."),
                               mail("v/inbox/301.", "Park update", "The zebra count is 12.")], {OWNER})
        conn.commit()
        refresh_stats(conn)
        memo, count = (conn.execute("SELECT item_id FROM item_refs WHERE ref = %s", (ref,)).fetchone()["item_id"]
                       for ref in ("v/inbox/300.", "v/inbox/301."))
        llm = FakeLLM()
        with Judge(db_url, Zebra()) as judge:
            r = ask(conn, judge, llm, "m", None, "How many zebras are there?")
    assert r.considered[:2] == (memo, count) and r.kept == (count, memo)      # search says memo; the judge, count
    assert llm.prompts[0].index("count is 12") < llm.prompts[0].index("planning memo")


def test_a_broken_draft_falls_back_to_the_larger_model(db_url):
    class Models:
        def __init__(self):
            self.calls = []

        def generate_json(self, model, system, user, schema, max_tokens=600):
            self.calls.append(model)
            if model == "small":
                raise ValueError("Unterminated string")                          # cut off mid-JSON
            return {"answer": "The sale completes on July 9.", "cites": [1]}

    llm = Models()
    with connect(db_url) as conn, Judge(db_url, Sale()) as judge:
        r = ask(conn, judge, llm, "big", None, "When does the pipeline sale complete?", draft="small")
    assert llm.calls == ["small", "big"] and r.answered_by == "big" and r.support.value == "yes"
