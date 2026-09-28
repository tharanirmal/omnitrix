"""Labelled examples for the judge, from ground truth the brain already has (LR §9): EnronQA's gold and wrong
answers, and the owner's own behaviour (did they reply? where did they file it?). No hand-labelling needed to
calibrate or fine-tune. Every example carries a `group` — its conversation — so that splits never separate a
message from the replies that quote it."""
from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import psycopg

from . import index
from .judge import Judge, Question, choice, noul
from .sources.enron import SYSTEM_FOLDERS
from .sources.enronqa import QA


@dataclass(frozen=True)
class Example:
    question: Question
    state: str
    subject: str                # what the judgement is about, e.g. 'item:12|qa:...'
    label: str
    source: str                 # labels.source: 'benchmark' or 'behaviour'
    group: str                  # the conversation it belongs to: splits keep a group together


def relevant_question(question: str) -> Question:
    return noul("relevant", f"Does this message contain the information needed to answer the question?"
                            f"\nQuestion: {question}")


def supported_question(question: str, answer: str) -> Question:
    return noul("supported", f"Is this answer to the question correct according to the material?"
                             f"\nQuestion: {question}\nAnswer: {answer}")


def item_texts(conn: psycopg.Connection, item_ids: Sequence[int]) -> dict[int, str]:
    """The material a judge sees for an item: subject, sender, what it says, then the history it quotes."""
    return {r["id"]: f"Subject: {r['subject']}\nFrom: {r['from_addr']}\n\n{r['body']}\n\n{r['quoted']}".strip()
            for r in conn.execute("SELECT id, subject, from_addr, body, quoted FROM items WHERE id = ANY(%s)",
                                  (list(item_ids),))}


def groups(conn: psycopg.Connection, item_ids: Sequence[int]) -> dict[int, str]:
    """Each item's conversation: its thread, or the item itself when it has no subject to thread on."""
    return {r["id"]: f"thread:{r['thread_key']}" if r["thread_key"] else f"item:{r['id']}" for r in
            conn.execute("SELECT id, thread_key FROM items WHERE id = ANY(%s)", (list(item_ids),))}


def answerable(conn: psycopg.Connection, qas: Sequence[QA]) -> tuple[list[QA], dict[str, int]]:
    """The questions whose email is in the brain, and the item holding each email."""
    ids = {r["ref"]: r["item_id"] for r in
           conn.execute("SELECT ref, item_id FROM item_refs WHERE ref = ANY(%s)", ([q.ref for q in qas],))}
    return [q for q in qas if q.ref in ids], ids


def supported(conn: psycopg.Connection, qas: Sequence[QA], n: int, rng: random.Random) -> list[Example]:
    """Is this answer to the question supported by the email? Gold answers vs EnronQA's wrong answers, balanced."""
    pool, ids = answerable(conn, qas)
    candidates = [q for q in pool if q.wrong]
    picked = rng.sample(candidates, min(n // 2, len(candidates)))
    texts = item_texts(conn, [ids[q.ref] for q in picked])
    group = groups(conn, [ids[q.ref] for q in picked])
    return [Example(supported_question(q.question, answer), texts[ids[q.ref]],
                    f"item:{ids[q.ref]}|qa:{q.qid}|{kind}", label, "benchmark", group[ids[q.ref]])
            for q in picked
            for answer, kind, label in ((q.gold, "gold", "yes"), (rng.choice(q.wrong), "wrong", "no"))]


def relevant(conn: psycopg.Connection, qas: Sequence[QA], n: int, rng: random.Random) -> list[Example]:
    """Does this email hold the answer to the question? The gold email vs the best keyword match from another
    thread (a hard negative), balanced. Both examples of a question share the gold email's group."""
    pool, ids = answerable(conn, qas)
    pairs: list[tuple[QA, int, str, int]] = []
    for q in rng.sample(pool, min(n // 2, len(pool))):
        gold = ids[q.ref]
        hits = [h.item_id for h in index.search(conn, None, q.question, k=10)]
        threads = groups(conn, [gold, *hits])
        negative = next((h for h in hits if h != gold and threads[h] != threads[gold]), None)
        if negative is not None:
            pairs += [(q, gold, "yes", gold), (q, negative, "no", gold)]
    texts = item_texts(conn, [item for _, item, _, _ in pairs])
    group = groups(conn, [gold for *_, gold in pairs])
    return [Example(relevant_question(q.question), texts[item], f"item:{item}|qa:{q.qid}", label, "benchmark",
                    group[gold])
            for q, item, label, gold in pairs]


def teach(conn: psycopg.Connection, judge: Judge, q: Question, n: int, rng: random.Random,
          on_item: Callable[[int], None] | None = None) -> int:
    """Teacher labels (LR §9): the judge's answers — give it the large model — on a random sample of items not yet
    labelled for `q`, stored as `teacher` labels. Every answer is also in the ledger. Returns how many were added."""
    from .memory import reading_text

    rows = conn.execute("SELECT i.id, i.subject, i.from_addr, i.body, i.quoted FROM items i WHERE length(i.body) > 20 "
                        "AND NOT EXISTS (SELECT 1 FROM labels l WHERE l.question = %s AND l.subject = 'item:' || i.id)",
                        (q.name,)).fetchall()
    added = 0
    for r in rng.sample(rows, min(n, len(rows))):
        v = judge.ask(q, reading_text(r), f"item:{r['id']}")
        if v.value:
            conn.execute("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, 'teacher') "
                         "ON CONFLICT DO NOTHING", (q.name, f"item:{r['id']}", v.value))
            conn.commit()
            added += 1
        if on_item:
            on_item(added)
    return added


def stored(conn: psycopg.Connection, q: Question, sources: Sequence[str] = ("human", "teacher")) -> list[Example]:
    """Examples for `q` from stored item labels; a label from an earlier source in `sources` wins (the owner over
    the teacher). The material is what the memory gate reads."""
    from .memory import reading_text

    best: dict[str, tuple[str, str]] = {}
    for r in conn.execute("SELECT subject, value, source FROM labels WHERE question = %s AND source = ANY(%s) "
                          "AND subject LIKE 'item:%%'", (q.name, list(sources))):
        if r["subject"] not in best or sources.index(r["source"]) < sources.index(best[r["subject"]][1]):
            best[r["subject"]] = (r["value"], r["source"])
    ids = [int(s.split(":")[1]) for s in best]
    rows = {r["id"]: r for r in conn.execute("SELECT id, subject, from_addr, body, quoted FROM items "
                                             "WHERE id = ANY(%s)", (ids,))}
    group = groups(conn, ids)
    return [Example(q, reading_text(rows[i]), f"item:{i}", best[f"item:{i}"][0], best[f"item:{i}"][1], group[i])
            for i in ids if i in rows]


def replied(conn: psycopg.Connection, n: int, rng: random.Random) -> list[Example]:
    """Did the owner reply? A received message counts as replied if the owner wrote in the same thread within
    14 days. Only threads with specific subjects (two or more words) are used; balanced."""
    rows = conn.execute(
        "SELECT i.id, EXISTS (SELECT 1 FROM items o WHERE o.direction = 'out' AND o.thread_key = i.thread_key "
        "  AND o.sent_at > i.sent_at AND o.sent_at <= i.sent_at + interval '14 days') AS replied "
        "FROM items i WHERE i.direction = 'in' AND i.thread_key LIKE '% %' "
        "AND i.sent_at BETWEEN '1998-01-01' AND '2002-12-31'").fetchall()
    yes = [r["id"] for r in rows if r["replied"]]
    no = [r["id"] for r in rows if not r["replied"]]
    k = min(n // 2, len(yes), len(no))
    picked = [(i, "yes") for i in rng.sample(yes, k)] + [(i, "no") for i in rng.sample(no, k)]
    texts = item_texts(conn, [i for i, _ in picked])
    group = groups(conn, [i for i, _ in picked])
    q = noul("replied", "Would the mailbox owner write a reply to this message?")
    return [Example(q, texts[i], f"item:{i}", label, "behaviour", group[i]) for i, label in picked]


def filed(conn: psycopg.Connection, n: int, rng: random.Random, folders: int = 12) -> list[Example]:
    """Which of their own folders did the owner file it in? Items kept in exactly one of the owner's `folders`
    largest hand-made folders; at most n / folders per folder (at least one), so no folder dominates."""
    rows = conn.execute(
        "SELECT item_id, array_agg(DISTINCT folder) AS f FROM item_refs "
        "WHERE split_part(folder, '/', 1) <> ALL(%s) GROUP BY item_id", (sorted(SYSTEM_FOLDERS),)).fetchall()
    sizes: dict[str, int] = {}
    for r in rows:
        for f in r["f"]:
            sizes[f] = sizes.get(f, 0) + 1
    top = sorted(sizes, key=lambda f: -sizes[f])[:folders]
    by_folder: dict[str, list[int]] = {f: [] for f in top}
    for r in rows:
        if len(r["f"]) == 1 and r["f"][0] in by_folder:
            by_folder[r["f"][0]].append(r["item_id"])
    per_folder = max(1, n // max(1, len(top)))
    picked = [(i, f) for f, ids in by_folder.items() for i in rng.sample(ids, min(len(ids), per_folder))]
    texts = item_texts(conn, [i for i, _ in picked])
    group = groups(conn, [i for i, _ in picked])
    q = choice("filed", "Which of the owner's folders does this message belong in?", sorted(top))
    return [Example(q, texts[i], f"item:{i}", f, "behaviour", group[i]) for i, f in picked]
