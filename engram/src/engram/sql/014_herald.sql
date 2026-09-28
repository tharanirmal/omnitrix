-- Herald: the one way engram reaches the owner (docs/research/agent-roster-review.md §2; brain-design D46/D47).
-- Every role posts cards here: Memory (a commitment coming due; a fulfils/contradicts check the owner settles),
-- Librarian (a fresh item that holds a meeting or commitment). Code rules route each card when it is posted: buzz
-- now, keep it for the digest, or drop it. The owner's taps go back to the role that asked, and into the ledger,
-- so the small judge's "notify?" question (D47) can later be learned from what the owner actually did.
CREATE TABLE herald_cards (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role          text        NOT NULL,                     -- memory | librarian
    kind          text        NOT NULL,                     -- due | fulfils | contradicts | arrival
    subject       text        NOT NULL UNIQUE,              -- what it is about; a card is posted once
    title         text        NOT NULL,
    body          text        NOT NULL DEFAULT '',
    actions       jsonb       NOT NULL,                     -- [{"id": "done", "label": "Done"}, ...]
    route         text        NOT NULL CHECK (route IN ('now', 'digest', 'drop')),
    why           text        NOT NULL,                     -- the rule that routed it, shown to the owner
    created_at    timestamptz NOT NULL DEFAULT now(),
    show_after    timestamptz NOT NULL DEFAULT now(),       -- snoozed until
    delivered_at  timestamptz,                              -- first reached a watch
    decided_at    timestamptz,
    decision      text,
    decided_by    text
);
CREATE INDEX herald_open ON herald_cards (show_after) WHERE decided_at IS NULL AND route <> 'drop';

-- Any process that posts or settles a card (the server, a memory build, the CLI) wakes the watch's long-poll.
CREATE FUNCTION herald_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('herald', NEW.id::text);
    RETURN NEW;
END $$;
CREATE TRIGGER herald_changed AFTER INSERT OR UPDATE OF route, show_after, decided_at ON herald_cards
    FOR EACH ROW EXECUTE FUNCTION herald_notify();

GRANT SELECT ON herald_cards TO engram_reader;
