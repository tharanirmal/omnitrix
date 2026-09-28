"""System 1: typed questions answered in one token, with probabilities read from the model's logits.

Three primitives with the same shapes as TypeSafe's Jev (LR §10.3a): `noul` (yes/no), `choice` (one of up to 26
labelled options) and `score` (ordered levels). `Judge.ask` puts a question to the small model (S1), calibrates the
answer (LR §8.1) and accepts it when it falls outside the uncertain band; otherwise the large model (S2) is asked
(LR §6, §8.2). An answer neither model settles is returned unsettled: it is a human's call. Every model answer is
appended to the hash-chained ledger (LR §11.5), which doubles as a cache (LR §2: past instances are reused)."""
from __future__ import annotations

import hashlib
import json
import math
import string
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
import psycopg
from psycopg.rows import dict_row

Kind = Literal["noul", "choice", "score"]
SYSTEM = ("You are a careful, literal judge. Read the material, then answer the question with exactly one of the "
          "allowed keys and nothing else.")
MAX_STATE_CHARS = 6000
GENESIS = "0" * 64
LEDGER_LOCK = 0x656E6772           # advisory lock serializing ledger appends ('engr')


# ------------------------------------------------------------------------------------------------ questions

@dataclass(frozen=True)
class Question:
    name: str                                    # decision type: calibration is per (name, model)
    kind: Kind
    instructions: str
    options: tuple[tuple[str, str], ...] = ()    # (label, description); for 'score', ordered low to high

    @property
    def keys(self) -> tuple[str, ...]:
        """The single tokens the model may answer with; each maps to one label."""
        return ("yes", "no") if self.kind == "noul" else tuple(string.ascii_uppercase[: len(self.options)])

    @property
    def labels(self) -> tuple[str, ...]:
        return ("yes", "no") if self.kind == "noul" else tuple(label for label, _ in self.options)

    def render(self, state: str) -> str:
        """Material first, question last: several questions about one item share the cached material prefix."""
        lines = ["Material:", state.strip()[:MAX_STATE_CHARS], "", "---", f"Question: {self.instructions}"]
        if self.kind == "noul":
            lines.append("Answer with one word: yes or no.")
        else:
            lines += [f"{k}) {label}" + (f": {desc}" if desc else "")
                      for k, (label, desc) in zip(self.keys, self.options, strict=True)]
            lines.append(f"Answer with one letter: {', '.join(self.keys)}.")
        return "\n".join(lines)


def noul(name: str, instructions: str) -> Question:
    return Question(name, "noul", instructions)


def choice(name: str, instructions: str, options: Mapping[str, str] | Sequence[str]) -> Question:
    opts = tuple(options.items()) if isinstance(options, Mapping) else tuple((o, "") for o in options)
    if not 2 <= len(opts) <= 26:
        raise ValueError("a choice needs 2-26 options (one letter each)")
    return Question(name, "choice", instructions, opts)


def score(name: str, instructions: str, levels: Sequence[str]) -> Question:
    if not 2 <= len(levels) <= 10:
        raise ValueError("a score needs 2-10 levels")
    return Question(name, "score", instructions, tuple((lvl, "") for lvl in levels))


# ------------------------------------------------------------------------------------------------- scoring

class ScoringError(RuntimeError):
    """The model's first token was none of the allowed keys."""


class Scorer(Protocol):
    model: str

    def score(self, system: str, user: str, keys: Sequence[str]) -> dict[str, float]:
        """Log-probability of each key as the first token of the answer."""
        ...


class OllamaScorer:
    """One forward pass, one output token; probabilities from Ollama's top-20 logprobs (LR §10.1)."""

    def __init__(self, url: str, model: str, timeout: float = 120.0):
        self.model = model
        self._http = httpx.Client(base_url=url.rstrip("/"), timeout=timeout)

    def score(self, system: str, user: str, keys: Sequence[str]) -> dict[str, float]:
        r = self._http.post("/api/chat", json={
            "model": self.model, "stream": False, "think": False, "keep_alive": "30m",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "logprobs": True, "top_logprobs": 20, "options": {"temperature": 0, "num_predict": 1}})
        r.raise_for_status()
        top = r.json()["logprobs"][0]["top_logprobs"]
        found: dict[str, list[float]] = {}
        for t in top:
            token = t["token"].strip()
            for k in keys:                        # keys match in any casing ('Yes', 'b')
                if token.lower() == k.lower():
                    found.setdefault(k, []).append(t["logprob"])
        if not found:
            raise ScoringError(f"{self.model} answered {top[0]['token']!r}, not one of {list(keys)}")
        floor = min(t["logprob"] for t in top) - 2.0     # a key outside the top 20 is rarer than all of them
        return {k: _logsumexp(found[k]) if k in found else floor for k in keys}

    def close(self) -> None:
        self._http.close()


class MLXScorer:
    """A local checkpoint, optionally with a fine-tuned LoRA adapter, run in-process with MLX: the logits of every
    key are read exactly (no top-k cap). Prompts use the same chat template as training (LR §9.3)."""

    def __init__(self, path: str, adapter: str | None = None):
        from mlx_lm import load  # optional dependency: `uv sync --extra finetune`

        self.lm, self.tokenizer = load(path, adapter_path=adapter)
        name = path.rstrip("/").rsplit("/", 1)[-1]
        self.model = f"mlx:{name}" + (f"+{adapter.rstrip('/').rsplit('/', 1)[-1]}" if adapter else "")
        self._ids: dict[str, list[int]] = {}

    def _variants(self, key: str) -> list[int]:
        """Token ids a key may be answered with, in any casing ('yes', 'Yes', 'b', 'B'); single tokens only."""
        if key not in self._ids:
            forms = {key, key.lower(), key.upper(), key.capitalize()}
            encoded = [self.tokenizer.encode(f, add_special_tokens=False) for f in forms]
            self._ids[key] = [ids[0] for ids in encoded if len(ids) == 1]
            if not self._ids[key]:
                raise ScoringError(f"key {key!r} is not a single token for {self.model}")
        return self._ids[key]

    def score(self, system: str, user: str, keys: Sequence[str]) -> dict[str, float]:
        import mlx.core as mx

        prompt = self.tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            add_generation_prompt=True, enable_thinking=False)
        logits = self.lm(mx.array(prompt)[None])[0, -1].astype(mx.float32)
        logprobs = logits - mx.logsumexp(logits)
        return {k: _logsumexp([float(logprobs[i]) for i in self._variants(k)]) for k in keys}


def make_scorer(spec: str, ollama_url: str) -> Scorer:
    """'qwen3:1.7b' is an Ollama model; 'mlx:<checkpoint>[@<adapter dir>]' runs in-process with MLX (a relative
    adapter directory is inside the project)."""
    if spec.startswith("mlx:"):
        from .config import ROOT

        path, _, adapter = spec.removeprefix("mlx:").partition("@")
        local = ROOT / path                                 # a model folder in the project, e.g. data/models/...
        return MLXScorer(str(local) if local.exists() else path, str(ROOT / adapter) if adapter else None)
    return OllamaScorer(ollama_url, spec)


# ------------------------------------------------------------------------------------------- calibration

@dataclass(frozen=True)
class Calibration:
    temperature: float = 1.0
    tau_lo: float = 0.1
    tau_hi: float = 0.9          # defaults until fitted: settle only confident answers (Appendix A of the LR)


def calibrated(logprobs: Mapping[str, float], temperature: float) -> dict[str, float]:
    scaled = {k: v / temperature for k, v in logprobs.items()}
    z = _logsumexp(list(scaled.values()))
    return {k: math.exp(v - z) for k, v in scaled.items()}


def is_settled(q: Question, probs: Mapping[str, float], cal: Calibration) -> bool:
    if q.kind == "noul":
        return probs["yes"] >= cal.tau_hi or probs["yes"] <= cal.tau_lo
    return max(probs.values()) >= cal.tau_hi


def load_calibration(conn: psycopg.Connection) -> dict[tuple[str, str], Calibration]:
    return {(r["question"], r["model"]): Calibration(r["temperature"], r["tau_lo"], r["tau_hi"])
            for r in conn.execute("SELECT question, model, temperature, tau_lo, tau_hi FROM calibration")}


def load_no_escalation(conn: psycopg.Connection) -> set[tuple[str, str, str]]:
    """(decision, S1 model, S2 model) where S2, measured on exactly what S1 escalates, is no more accurate than S1
    (evaluate.py): asking it would only add latency or error, so an unsure S1 answer goes to the owner (LR §10.5)."""
    out = set()
    for r in conn.execute("SELECT question, model, metrics -> 'escalated_from' AS e FROM calibration "
                          "WHERE metrics ? 'escalated_from'"):
        for s1_model, m in r["e"].items():
            if None not in (m.get("s1_accuracy"), m.get("s2_accuracy")) and m["s2_accuracy"] <= m["s1_accuracy"]:
                out.add((r["question"], s1_model, r["model"]))
    return out


# ----------------------------------------------------------------------------------------------- judging

@dataclass(frozen=True)
class Answer:
    tier: str                    # 'S1' or 'S2'
    model: str
    logprobs: dict[str, float]   # raw, per label ({} if the model gave no valid key)
    probs: dict[str, float]      # calibrated, per label
    value: str                   # most probable label ('' if invalid)
    settled: bool
    latency_ms: float            # 0 when served from the ledger


@dataclass(frozen=True)
class Verdict:
    question: str
    subject: str
    value: str
    probs: dict[str, float]
    settled: bool                # False: neither model is sure -> a human's call
    tier: str                    # the tier whose answer is final
    answers: tuple[Answer, ...]

    @property
    def p(self) -> float:
        return self.probs.get(self.value, 0.0)


class Judge:
    """Owns its own autocommit connection: every ledger append is durable at once and never commits a caller's
    unrelated work."""

    def __init__(self, url: str, s1: Scorer | None, s2: Scorer | None = None):
        if s1 is None and s2 is None:
            raise ValueError("a judge needs at least one model")
        self.conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        self.s1, self.s2 = s1, s2       # s1=None: an S2-only decision (e.g. intent, LR §11.1)
        self.calibration = load_calibration(self.conn)
        self.no_escalation = load_no_escalation(self.conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Judge:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def ask(self, q: Question, state: str, subject: str) -> Verdict:
        """S1 first; S2 only when S1 is unsure and S2 is measured to do better on such cases. Unsettled: a human's
        call."""
        answers: list[Answer] = []
        for tier, scorer in (("S1", self.s1), ("S2", self.s2)):
            if scorer is None or (answers and (q.name, answers[0].model, scorer.model) in self.no_escalation):
                continue
            answers.append(self.answer(tier, scorer, q, state, subject))
            if answers[-1].settled:
                break
        final = answers[-1]
        return Verdict(q.name, subject, final.value, final.probs, final.settled, final.tier, tuple(answers))

    def answer(self, tier: str, scorer: Scorer, q: Question, state: str, subject: str) -> Answer:
        """One model's answer: from the ledger if this model already answered this exact prompt, else scored."""
        user = q.render(state)
        key = _sha256(f"{q.name}\x1f{SYSTEM}\x1f{user}")
        row = self.conn.execute("SELECT logprobs FROM judgements WHERE question = %s AND input_hash = %s "
                                "AND model = %s ORDER BY id DESC LIMIT 1", (q.name, key, scorer.model)).fetchone()
        latency = 0.0
        if row is not None:
            logprobs = row["logprobs"]
        else:
            t0 = time.monotonic()
            try:
                raw = scorer.score(SYSTEM, user, q.keys)
                logprobs = {label: _num(raw[k]) for k, label in zip(q.keys, q.labels, strict=True)}
            except ScoringError:
                logprobs = {}                      # an invalid answer is never settled: it escalates (LR §5),
                                                   # to S2 or, where S2 is measured no better, to the owner
            latency = (time.monotonic() - t0) * 1000
        cal = self.calibration.get((q.name, scorer.model), Calibration())
        if logprobs:
            probs = calibrated(logprobs, cal.temperature)
            value, settled = max(probs, key=probs.__getitem__), is_settled(q, probs, cal)
        else:
            probs, value, settled = {label: 1 / len(q.labels) for label in q.labels}, "", False
        answer = Answer(tier, scorer.model, logprobs, probs, value, settled, latency)
        if row is None:
            append(self.conn, q.name, subject, key, answer)
        return answer


# ------------------------------------------------------------------------------------------------ ledger

def append(conn: psycopg.Connection, question: str, subject: str, input_hash: str, a: Answer) -> None:
    """Append one answer to the ledger in its own transaction; the advisory lock keeps the chain linear."""
    probs = {k: _num(v) for k, v in a.probs.items()}
    record = [question, subject, input_hash, a.tier, a.model, a.logprobs, probs, a.value, a.settled]
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LEDGER_LOCK,))
        last = conn.execute("SELECT hash FROM judgements ORDER BY id DESC LIMIT 1").fetchone()
        prev = last["hash"] if last else GENESIS
        conn.execute(
            "INSERT INTO judgements (question, subject, input_hash, tier, model, logprobs, probs, value, settled, "
            "latency_ms, prev_hash, hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (question, subject, input_hash, a.tier, a.model, json.dumps(a.logprobs), json.dumps(probs), a.value,
             a.settled, round(a.latency_ms, 2), prev, _chain(prev, record)))


def verify_ledger(conn: psycopg.Connection) -> int | None:
    """Id of the first row whose content or link no longer matches the chain; None if intact."""
    prev = GENESIS
    for r in conn.execute("SELECT id, question, subject, input_hash, tier, model, logprobs, probs, value, settled, "
                          "prev_hash, hash FROM judgements ORDER BY id"):
        record = [r["question"], r["subject"], r["input_hash"], r["tier"], r["model"], r["logprobs"], r["probs"],
                  r["value"], r["settled"]]
        if r["prev_hash"] != prev or r["hash"] != _chain(prev, record):
            return r["id"]
        prev = r["hash"]
    return None


def _chain(prev: str, record: list) -> str:
    return _sha256(prev + json.dumps(record, sort_keys=True, separators=(",", ":")))


def _num(x: float) -> float:
    """Six decimals, and never -0.0: jsonb stores -0.0 as 0.0, which would break the hash chain."""
    return round(x, 6) + 0.0


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _logsumexp(values: Sequence[float]) -> float:
    m = max(values)
    return m + math.log(sum(math.exp(v - m) for v in values))
