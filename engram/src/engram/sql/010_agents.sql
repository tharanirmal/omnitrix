-- Round 3: what AI agents need from the brain (docs/research/handoff-round3-agent-queries.md).

-- People as entities: one row per person, with every address and name they appear under ("Vince", "Vince
-- Kaminski", vince.kaminski@enron.com, vkaminski@aol.com). Rebuilt by people.py from items and beliefs.
CREATE TABLE people (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       text   NOT NULL,                     -- display name, e.g. 'Vince Kaminski'
    key        text   NOT NULL UNIQUE,              -- normalized 'first last' (or the address when no name)
    addresses  text[] NOT NULL DEFAULT '{}',
    aliases    text[] NOT NULL DEFAULT '{}',        -- lower-cased names beliefs and notes use for them
    n_items    int    NOT NULL DEFAULT 0
);
CREATE INDEX people_addresses ON people USING gin (addresses);
CREATE INDEX people_aliases ON people USING gin (aliases);

-- Trust tiers for recalled memory (after OpenJarvis's fail-closed recall): what the owner wrote or confirmed, what
-- the owner's own mail says, what others' mail says, and what was screened as a possible prompt injection (never
-- served to a model as evidence).
ALTER TABLE beliefs ADD COLUMN trust text NOT NULL DEFAULT 'external'
    CHECK (trust IN ('owner', 'engram', 'external', 'quarantined'));
UPDATE beliefs b SET trust = CASE WHEN b.author = 'owner' THEN 'owner'
                                  WHEN i.direction = 'out' THEN 'engram' ELSE 'external' END
FROM items i WHERE i.id = b.item_id;
DROP VIEW current_beliefs;
CREATE VIEW current_beliefs AS
SELECT b.*, i.subject, i.sent_at FROM beliefs b JOIN items i ON i.id = b.item_id WHERE upper_inf(b.recorded);

-- Which embedder made each vector, so a new embedder re-embeds only what it has not made (after OpenJarvis).
ALTER TABLE chunks ADD COLUMN embedding_model text;
UPDATE chunks SET embedding_model = 'bge-m3' WHERE embedding IS NOT NULL;

GRANT SELECT ON people TO engram_reader;
