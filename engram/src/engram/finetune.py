"""Fine-tuning the personal System 1 judge (LR §9): labelled examples -> chat-format JSONL, split by conversation
so the model is never tested on a thread it trained on (replies quote earlier messages verbatim) -> LoRA with
mlx-lm, loss on the answer only -> an adapter that `judge.MLXScorer` loads. Knowledge stays in the database; only
the judging skill goes into the weights."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from .judge import SYSTEM, noul
from .labels import Example

SPLITS = (("test", 0.2), ("valid", 0.1), ("train", 0.7))


def split_of(group: str) -> str:
    """Train, valid or test for a conversation; every example in one group lands in the same split."""
    x = int(hashlib.sha256(group.encode()).hexdigest(), 16) % 1000 / 1000
    edge = 0.0
    for name, share in SPLITS:
        edge += share
        if x < edge:
            return name
    return "train"


def chat(e: Example) -> dict:
    """One training row: the exact system and user text the judge sends, and the answer key as the reply."""
    key = e.question.keys[e.question.labels.index(e.label)]
    return {"messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": e.question.render(e.state)},
                         {"role": "assistant", "content": key}]}


def write_dataset(examples: Sequence[Example], out: Path, seed: int = 0,
                  repeat: dict[str, int] | None = None) -> dict[str, Counter]:
    """train/valid/test.jsonl under `out`, shuffled; returns the count per decision in each split. `repeat` shows
    a small decision's training rows several times, so ~150 examples are not drowned by thousands of others;
    valid and test rows are never repeated."""
    out.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict]] = {name: [] for name, _ in SPLITS}
    counts: dict[str, Counter] = {name: Counter() for name, _ in SPLITS}
    for e in examples:
        split = split_of(e.group)
        k = (repeat or {}).get(e.question.name, 1) if split == "train" else 1
        rows[split] += [chat(e)] * k
        counts[split][e.question.name] += k
    rng = random.Random(seed)
    for name, items in rows.items():
        rng.shuffle(items)
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
    return counts


def check_template(tokenizer) -> None:
    """Fail fast unless training and inference see the same tokens: mlx-lm renders each training row with the
    tokenizer's chat template, while MLXScorer renders the prompt with thinking disabled. The rendered training
    row must begin with exactly the inference prompt, so the answer token follows the same context."""
    probe = Example(noul("probe", "Is this a probe?"), "probe", "probe", "yes", "benchmark", "probe")
    row = chat(probe)["messages"]
    trained = tokenizer.apply_chat_template(row)
    inferred = tokenizer.apply_chat_template(row[:-1], add_generation_prompt=True, enable_thinking=False)
    if trained[:len(inferred)] != inferred:
        raise RuntimeError("chat template mismatch: training rows do not start with the inference prompt")


MAX_TOKENS = 2048                   # mlx-lm's max_seq_length: longer rows are cut from the end


def fit(data: Path, tokenizer, max_tokens: int = MAX_TOKENS) -> Path:
    """The dataset without rows too long to train on. mlx-lm cuts an over-long row from the end, which removes the
    answer; with the prompt masked, no token carries loss, the loss is 0/0 and one such row turns the weights to
    NaN (hidden at batch 4 by the other rows, fatal at batch 1). Returns `data` itself when nothing is too long,
    else a sibling directory `<data>-fit` with those rows left out of train and valid (test is copied as is)."""
    keep: dict[str, list[str]] = {}
    dropped = 0
    for split in ("train", "valid"):
        lines = (data / f"{split}.jsonl").read_text().splitlines()
        keep[split] = [ln for ln in lines if len(tokenizer.apply_chat_template(json.loads(ln)["messages"]))
                       <= max_tokens]
        dropped += len(lines) - len(keep[split])
    if not dropped:
        return data
    out = data.with_name(f"{data.name}-fit")
    out.mkdir(exist_ok=True)
    for split, lines in keep.items():
        (out / f"{split}.jsonl").write_text("".join(ln + "\n" for ln in lines))
    if (data / "test.jsonl").exists():
        (out / "test.jsonl").write_text((data / "test.jsonl").read_text())
    print(f"left out {dropped} rows longer than {max_tokens} tokens; training on {out}", file=sys.stderr)
    return out


def train(base: str, data: Path, adapter: Path, iters: int, batch_size: int = 4, learning_rate: float = 1e-4,
          num_layers: int = 16, accumulate: int = 1, resume: Path | None = None) -> None:
    """LoRA on `base` with mlx-lm; the prompt is masked, so only the answer tokens carry loss. `accumulate` > 1
    keeps the effective batch at batch_size x accumulate with a smaller peak: the 24 GB Mac then has room for
    another model (the 14B alone takes ~9.5 GB)."""
    from huggingface_hub import snapshot_download
    from mlx_lm.utils import load_tokenizer  # optional dependency: `uv sync --extra finetune`

    tokenizer = load_tokenizer(Path(snapshot_download(base)))
    check_template(tokenizer)
    data = fit(data, tokenizer)
    subprocess.run([sys.executable, "-m", "mlx_lm.lora", "--model", base, "--train", "--data", str(data),
                    "--adapter-path", str(adapter), "--mask-prompt", "--iters", str(iters),
                    "--batch-size", str(batch_size), "--learning-rate", str(learning_rate),
                    "--num-layers", str(num_layers), "--grad-checkpoint",
                    "--grad-accumulation-steps", str(accumulate),
                    *(["--resume-adapter-file", str(resume)] if resume else [])], check=True)

