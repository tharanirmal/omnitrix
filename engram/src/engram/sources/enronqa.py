"""EnronQA (Ryan et al. 2025, CC BY 4.0; LR §3.5): questions about emails in the same mailboxes, each with a gold
answer and plausible wrong answers. Ground truth for retrieval and for the judge; never ingested as memory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.dataset as ds


@dataclass(frozen=True, slots=True)
class QA:
    qid: str                    # '<ref>#<n>'
    ref: str                    # the email's original location, as in item_refs.ref
    question: str
    gold: str
    wrong: tuple[str, ...]


def read_qa(path: Path, owner: str) -> list[QA]:
    table = ds.dataset(path, format="parquet").to_table(
        columns=["path", "questions", "gold_answers", "incorrect_answers"], filter=pc.field("user") == owner)
    out: list[QA] = []
    for r in table.to_pylist():
        wrong = r["incorrect_answers"] or []
        for i, (question, gold) in enumerate(zip(r["questions"] or [], r["gold_answers"] or [], strict=False)):
            out.append(QA(f"{r['path']}#{i}", r["path"], question, gold, tuple(wrong[i] if i < len(wrong) else ())))
    return out
