-- engram core: the owner's raw items (episodes), where each was originally kept, and retrieval chunks.
-- Raw items are the ground truth and are never rewritten (LR §3.6: store raw, gate only extraction).

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per distinct piece of the owner's data. The same email kept in several folders collapses
-- on content_hash; item_refs keeps every original location.
CREATE TABLE items (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source        text        NOT NULL,                -- connector, e.g. 'enron'
    kind          text        NOT NULL,                -- 'email' (later 'meeting', 'note', ...)
    content_hash  text        NOT NULL UNIQUE,
    sent_at       timestamptz,
    from_addr     text        NOT NULL DEFAULT '',
    to_addrs      text[]      NOT NULL DEFAULT '{}',
    cc_addrs      text[]      NOT NULL DEFAULT '{}',
    subject       text        NOT NULL DEFAULT '',
    body          text        NOT NULL,                -- what this item itself says (quoted history removed)
    quoted        text        NOT NULL DEFAULT '',     -- quoted or forwarded history, kept for audit and fallback
    thread_key    text        NOT NULL DEFAULT '',     -- normalized subject; a thread's messages share it
    direction     text        NOT NULL CHECK (direction IN ('in', 'out')),   -- relative to the owner
    ingested_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX items_sent_at ON items (sent_at);
CREATE INDEX items_from    ON items (from_addr);
CREATE INDEX items_to      ON items USING gin (to_addrs);
CREATE INDEX items_cc      ON items USING gin (cc_addrs);
CREATE INDEX items_thread  ON items (thread_key);

CREATE TABLE item_refs (
    ref      text   PRIMARY KEY,                        -- original location, e.g. 'kaminski-v/inbox/123.'
    item_id  bigint NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    folder   text   NOT NULL                            -- where the owner kept it: a personal label (LR §9)
);
CREATE INDEX item_refs_item ON item_refs (item_id);

CREATE TABLE chunks (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id    bigint   NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    ord        smallint NOT NULL,
    header     text     NOT NULL,                       -- date | from | to | subject: embedded and searched with the text
    text       text     NOT NULL,
    tsv        tsvector GENERATED ALWAYS AS (to_tsvector('english', header || ' ' || text)) STORED,
    embedding  halfvec(1024),                           -- NULL until `engram index`; half the storage of vector
    UNIQUE (item_id, ord)
);
CREATE INDEX chunks_tsv ON chunks USING gin (tsv);
-- The HNSW index is created by `engram index` after the first bulk embedding pass.

-- Who the owner deals with, derived on the fly.
CREATE VIEW contacts AS
SELECT addr,
       count(*) FILTER (WHERE role = 'sender')    AS emails_from,
       count(*) FILTER (WHERE role = 'recipient') AS emails_to,
       min(sent_at) AS first_seen,
       max(sent_at) AS last_seen
FROM (SELECT from_addr AS addr, 'sender' AS role, sent_at FROM items WHERE direction = 'in'
      UNION ALL
      SELECT unnest(to_addrs || cc_addrs), 'recipient', sent_at FROM items WHERE direction = 'out') t
WHERE addr <> ''
GROUP BY addr;
