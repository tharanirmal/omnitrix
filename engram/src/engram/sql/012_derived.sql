-- Derived labels for adapter v2 (docs/research/agent-roster-review.md §4, §6): labels read off structure the brain
-- already has (a verified meeting belief, a superseded time, the actor's "attached" in the thread), each shown to
-- the owner's team once on the labelling page. A human label beats a derived one. `label_examples` keeps the exact
-- material the judge will see, so the team checks, training and evaluation all read the same text.
ALTER TABLE labels DROP CONSTRAINT labels_source_check;
ALTER TABLE labels ADD CONSTRAINT labels_source_check
    CHECK (source IN ('human', 'behaviour', 'benchmark', 'teacher', 'derived'));

CREATE TABLE label_examples (
    question    text        NOT NULL,
    subject     text        NOT NULL,           -- e.g. 'item:12', 'belief:3|item:40', 'belief:3|belief:9'
    state       text        NOT NULL,           -- the material, rendered exactly as the judge sees it at runtime
    grp         text        NOT NULL,           -- its conversation: training splits keep a group together
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (question, subject)
);
