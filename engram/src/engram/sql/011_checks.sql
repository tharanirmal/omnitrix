-- Memory's two checks (docs/research/agent-roster-review.md §2, brain-design D26 and D27): a later item that
-- carries out an open commitment, and a new belief that cannot be true together with a current decision or
-- commitment. Each link is the judge's finding with its probability. A settled "fulfils" closes the commitment
-- (status 'done'); everything else waits for the owner, who confirms or rejects it. Links are never deleted.
CREATE TABLE belief_links (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        text        NOT NULL CHECK (kind IN ('fulfils', 'contradicts')),
    belief_id   bigint      NOT NULL REFERENCES beliefs (id),  -- the earlier commitment or decision
    item_id     bigint      NOT NULL REFERENCES items (id),    -- the item that fulfils or contradicts it
    new_belief  bigint      REFERENCES beliefs (id),           -- for 'contradicts': the belief the item gave
    p           real        NOT NULL,                          -- the judge's calibrated P(yes)
    settled     boolean     NOT NULL,                          -- false: the judge was unsure, the owner decides
    verdict     text        NOT NULL DEFAULT 'pending' CHECK (verdict IN ('pending', 'confirmed', 'rejected')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, belief_id, item_id)
);
CREATE INDEX belief_links_belief ON belief_links (belief_id);
CREATE INDEX belief_links_open ON belief_links (kind) WHERE verdict = 'pending';

GRANT SELECT ON belief_links TO engram_reader;
