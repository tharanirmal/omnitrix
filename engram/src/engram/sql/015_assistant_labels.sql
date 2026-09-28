-- Adapter v2's checks, done by the assistant at the owner's request (28 Sep 2026) instead of the team: kept as
-- their own source so they are never mistaken for the owner's. A human check still beats them; derived labels
-- rank last. The public Enron data is what was read; the owner's own labels (Obsidian, the watch) stay 'human'.
ALTER TABLE labels DROP CONSTRAINT labels_source_check;
ALTER TABLE labels ADD CONSTRAINT labels_source_check
    CHECK (source IN ('human', 'assistant', 'behaviour', 'benchmark', 'teacher', 'derived'));
