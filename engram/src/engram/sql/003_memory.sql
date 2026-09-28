-- Memory: beliefs the brain distils from items — commitments, decisions and meetings (LR §1, §3.6).
-- Bitemporal: `valid` is when a belief holds in the world, `recorded` is when the brain held it. Revising a belief
-- closes its `recorded` range and adds a successor that points back to it; nothing is deleted.

CREATE TABLE beliefs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        text        NOT NULL CHECK (kind IN ('commitment', 'decision', 'meeting')),
    actor       text        NOT NULL,           -- who commits / decided / sets up the meeting
    other       text        NOT NULL DEFAULT '',-- to whom / with whom
    statement   text        NOT NULL,           -- one line, third person
    due_at      timestamptz,                    -- deadline or meeting time, resolved in code from `when_text`
    when_text   text        NOT NULL DEFAULT '',-- the words the email used for the time
    status      text        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'dropped')),
    valid       tstzrange   NOT NULL,           -- from the item's date; open-ended until something ends it
    recorded    tstzrange   NOT NULL DEFAULT tstzrange(now(), NULL),
    item_id     bigint      NOT NULL REFERENCES items (id),
    quote       text        NOT NULL,           -- verbatim sentence it came from (checked to occur in the item)
    confidence  real        NOT NULL,           -- calibrated probability of the gate that admitted it
    supersedes  bigint      REFERENCES beliefs (id)
);
CREATE INDEX beliefs_current ON beliefs (kind, due_at) WHERE upper_inf(recorded);
CREATE INDEX beliefs_item    ON beliefs (item_id);
CREATE INDEX beliefs_actor   ON beliefs (actor) WHERE upper_inf(recorded);

-- What the brain believes now.
CREATE VIEW current_beliefs AS
SELECT b.*, i.subject, i.sent_at FROM beliefs b JOIN items i ON i.id = b.item_id WHERE upper_inf(b.recorded);

-- Which items the memory builder has already read, so re-runs only process new items.
CREATE TABLE memory_scans (
    item_id     bigint      PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
    kinds       text[]      NOT NULL,           -- what the gate found: subset of commitment/decision/meeting
    scanned_at  timestamptz NOT NULL DEFAULT now()
);
