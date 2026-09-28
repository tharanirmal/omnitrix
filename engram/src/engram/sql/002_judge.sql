-- System 1 / System 2 judgements, their ground truth, and per-model calibration (LR §8, §11.5).

-- Every model answer to a typed question, append-only and hash-chained: altering or deleting a row breaks the
-- chain from that row on (verify with engram.judge.verify_ledger). Doubles as a cache: the same question on the
-- same material is never scored twice by the same model.
CREATE TABLE judgements (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question    text        NOT NULL,           -- decision type, e.g. 'supported'
    subject     text        NOT NULL,           -- what it is about, e.g. 'item:123' or 'item:123|qa:...'
    input_hash  text        NOT NULL,           -- hash of the exact prompt
    tier        text        NOT NULL CHECK (tier IN ('S1', 'S2', 'H')),
    model       text        NOT NULL,
    logprobs    jsonb       NOT NULL,           -- raw, per label: lets calibration be refitted without re-running
    probs       jsonb       NOT NULL,           -- calibrated, per label, as used for this decision
    value       text        NOT NULL,           -- most probable label ('' if the model gave no valid key)
    settled     boolean     NOT NULL,           -- outside this model's uncertain band
    latency_ms  real        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    prev_hash   text        NOT NULL,
    hash        text        NOT NULL UNIQUE
);
CREATE INDEX judgements_cache   ON judgements (question, input_hash, model);
CREATE INDEX judgements_subject ON judgements (subject);

-- Ground truth: from the owner's behaviour (replies, filing), benchmarks, a teacher model, or a human correction.
CREATE TABLE labels (
    question    text        NOT NULL,
    subject     text        NOT NULL,
    value       text        NOT NULL,
    source      text        NOT NULL CHECK (source IN ('human', 'behaviour', 'benchmark', 'teacher')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (question, subject, source)
);

-- Temperature and the uncertain band per (decision type, model), fitted on labelled answers.
CREATE TABLE calibration (
    question     text        NOT NULL,
    model        text        NOT NULL,
    temperature  real        NOT NULL,
    tau_lo       real        NOT NULL,          -- noul: P(yes) at or below this settles 'no'
    tau_hi       real        NOT NULL,          -- noul: P(yes) at or above settles 'yes'; choice: top probability
    metrics      jsonb       NOT NULL DEFAULT '{}',
    fitted_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (question, model)
);
