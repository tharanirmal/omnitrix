-- The brain: document metadata, entity mentions, document links and a log of every recall.

ALTER TABLE documents ADD COLUMN occurred_at timestamptz;          -- email date, note date, file date
ALTER TABLE documents ADD COLUMN meta jsonb NOT NULL DEFAULT '{}';  -- demo_id, path, filename, email_id...
CREATE INDEX documents_source ON documents (source_id);

-- Each chunk keeps a one-line header (document title, date, sender) that is embedded and searched with it,
-- so a chunk can be found by its email subject even when the body never repeats it.
ALTER TABLE chunks ADD COLUMN context text NOT NULL DEFAULT '';

-- Search with an English dictionary (stemming: "decided" finds "decision") instead of 'simple'.
DROP INDEX chunks_tsv;
ALTER TABLE chunks DROP COLUMN tsv;
ALTER TABLE chunks ADD COLUMN tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', context || ' ' || text)) STORED;
CREATE INDEX chunks_tsv ON chunks USING gin (tsv);
ALTER TABLE chunks ADD COLUMN entity_ids text[] NOT NULL DEFAULT '{}';  -- entities named in this chunk
CREATE INDEX chunks_document ON chunks (document_id);
CREATE INDEX chunks_entities ON chunks USING gin (entity_ids);

-- Which document mentions which person / organization / project, and how we know.
CREATE TABLE mentions (
    document_id  text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id    text NOT NULL REFERENCES entities(id),
    how          text NOT NULL,        -- sender, recipient, text, frontmatter, domain
    PRIMARY KEY (document_id, entity_id, how)
);
CREATE INDEX mentions_entity ON mentions (entity_id);

-- Document-to-document links: a reply and its parent, an attachment and its email.
CREATE TABLE document_links (
    from_doc  text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    to_doc    text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    type      text NOT NULL CHECK (type IN ('reply_to', 'attachment_of')),
    PRIMARY KEY (from_doc, to_doc, type)
);

-- Every recall an agent makes: what it asked, what the brain narrowed down to, what it returned.
-- The graph page replays these to show which part of the brain each question touched.
CREATE TABLE recall_log (
    id           text PRIMARY KEY,
    agent        text NOT NULL,
    strategy     text NOT NULL,        -- brain, vector_all, keyword_all
    query        text NOT NULL,
    entity_ids   text[] NOT NULL DEFAULT '{}',
    scope_docs   text[] NOT NULL DEFAULT '{}',
    returned     jsonb NOT NULL DEFAULT '[]',   -- [{chunk_id, document_id, score, why}]
    facts        jsonb NOT NULL DEFAULT '[]',
    stats        jsonb NOT NULL DEFAULT '{}',
    at           timestamptz NOT NULL,          -- demo clock
    recorded_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
