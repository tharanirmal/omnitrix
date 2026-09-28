-- Obsidian as two-way memory (round2-plan.md §B). The owner's edits in the vault become beliefs they author; the
-- vault_files table remembers which file mirrors what and the content engram last wrote, so an edit by the owner
-- is noticed (hash differs) and never overwritten.
ALTER TABLE beliefs ADD COLUMN author text NOT NULL DEFAULT 'engram' CHECK (author IN ('engram', 'owner'));

DROP VIEW current_beliefs;
CREATE VIEW current_beliefs AS
SELECT b.*, i.subject, i.sent_at FROM beliefs b JOIN items i ON i.id = b.item_id WHERE upper_inf(b.recorded);

CREATE TABLE vault_files (
    path          text        PRIMARY KEY,              -- relative to the vault
    kind          text        NOT NULL CHECK (kind IN ('belief', 'person', 'source', 'review', 'note')),
    ref_id        bigint      NOT NULL,                 -- belief, item, or 0 for people
    exported_hash text        NOT NULL,                 -- sha256 of what engram last wrote (or read, for notes)
    synced_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX vault_files_ref ON vault_files (kind, ref_id);
