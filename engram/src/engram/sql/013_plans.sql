-- Planner (docs/research/agent-roster-review.md §2; H §3: the model extracts, a solver schedules). One row per
-- task per plan version: re-planning adds a new version and marks what the previous one missed, so the day's
-- history of plans is kept and the latest version is the plan.
CREATE TABLE plan_entries (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    day         date        NOT NULL,
    version     int         NOT NULL,
    belief_id   bigint      REFERENCES beliefs (id),           -- NULL for a protected block (lunch, personal)
    title       text        NOT NULL,
    starts      timestamptz,                                    -- NULL: did not fit today (bumped)
    ends        timestamptz,
    kind        text        NOT NULL CHECK (kind IN ('task', 'meeting', 'protected')),
    status      text        NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'done', 'missed', 'bumped')),
    why         text        NOT NULL DEFAULT '',                -- the priority reasons, shown to the owner
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX plan_entries_day ON plan_entries (day, version);

GRANT SELECT ON plan_entries TO engram_reader;
