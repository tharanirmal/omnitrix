-- Omnitrix: the second brain's single source of truth.
-- Sections: knowledge, work, memory, agents, control. Mem0 creates and manages its own tables.
-- Conventions: text ids with prefixes (see omnitrix/core/ids.py); demo-clock times in *_at columns;
-- recorded_at / created_at use the real clock (now()) for auditing.

CREATE EXTENSION IF NOT EXISTS vector;

-- ================================================================================== KNOWLEDGE

CREATE TABLE sources (
    id            text PRIMARY KEY,
    type          text NOT NULL CHECK (type IN ('email', 'file', 'obsidian_note', 'voice_note', 'calendar',
                                                'web', 'manual')),
    location      text NOT NULL,                  -- mailpit://msg/<id>, file path, vault path
    content_hash  text,
    received_at   timestamptz NOT NULL,
    processed_at  timestamptz,
    meta          jsonb NOT NULL DEFAULT '{}',
    UNIQUE (location, content_hash)
);

CREATE TABLE emails (
    id            text PRIMARY KEY,
    source_id     text REFERENCES sources(id),
    message_id    text NOT NULL UNIQUE,           -- RFC 5322 Message-ID: the same email is stored once
    thread_id     text,
    in_reply_to   text,
    direction     text NOT NULL DEFAULT 'in' CHECK (direction IN ('in', 'out')),
    from_addr     text NOT NULL,
    to_addrs      text[] NOT NULL DEFAULT '{}',
    cc_addrs      text[] NOT NULL DEFAULT '{}',
    subject       text NOT NULL DEFAULT '',
    body_text     text NOT NULL DEFAULT '',
    received_at   timestamptz NOT NULL
);
CREATE INDEX emails_thread ON emails (thread_id);

CREATE TABLE documents (
    id            text PRIMARY KEY,
    source_id     text NOT NULL REFERENCES sources(id),
    title         text NOT NULL DEFAULT '',
    doc_type      text NOT NULL DEFAULT 'other',  -- email, note, contract, invoice, report, transcript...
    full_text     text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id            text PRIMARY KEY,
    document_id   text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position      int NOT NULL,
    text          text NOT NULL,
    embedding     vector(1024),                   -- = OMNITRIX_EMBED_DIM (bge-m3)
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);
CREATE INDEX chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv ON chunks USING gin (tsv);

CREATE TABLE entities (
    id            text PRIMARY KEY,
    type          text NOT NULL CHECK (type IN ('person', 'organization', 'project', 'place', 'other')),
    name          text NOT NULL,
    aliases       text[] NOT NULL DEFAULT '{}',
    importance    smallint NOT NULL DEFAULT 1 CHECK (importance BETWEEN 0 AND 3),  -- 0 low .. 3 key
    details       jsonb NOT NULL DEFAULT '{}',
    embedding     vector(1024),                   -- fuzzy name matching: "Mr. Mehta" = "R. Mehta"
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX entities_name ON entities (lower(name));

CREATE TABLE relations (
    id            text PRIMARY KEY,
    from_entity   text NOT NULL REFERENCES entities(id),
    to_entity     text NOT NULL REFERENCES entities(id),
    type          text NOT NULL,                  -- works_at, client_of, owns, depends_on, reports_to...
    valid_from    timestamptz,
    valid_to      timestamptz,                    -- NULL = still true; never delete, close it instead
    source_id     text REFERENCES sources(id),
    confidence    real NOT NULL DEFAULT 1.0,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX relations_from ON relations (from_entity);
CREATE INDEX relations_to ON relations (to_entity);

-- ======================================================================================= WORK

CREATE TABLE tasks (
    id                  text PRIMARY KEY,
    title               text NOT NULL,
    action_type         text NOT NULL,
    source_id           text REFERENCES sources(id),
    email_id            text REFERENCES emails(id),
    evidence_quote      text NOT NULL DEFAULT '',
    owner               text NOT NULL DEFAULT 'me',
    requested_by        text REFERENCES entities(id),
    related_entities    text[] NOT NULL DEFAULT '{}',
    due_at              timestamptz,
    due_type            text NOT NULL DEFAULT 'none' CHECK (due_type IN ('hard', 'soft', 'none')),
    earliest_start      timestamptz,
    estimate_minutes    int NOT NULL DEFAULT 30,
    estimate_basis      text NOT NULL DEFAULT 'default',
    energy              text NOT NULL DEFAULT 'any' CHECK (energy IN ('focus', 'admin', 'any')),
    can_split           boolean NOT NULL DEFAULT false,
    priority_score      smallint NOT NULL DEFAULT 0 CHECK (priority_score BETWEEN 0 AND 100),
    priority_reasons    jsonb NOT NULL DEFAULT '[]',
    blocked_by          text[] NOT NULL DEFAULT '{}',
    status              text NOT NULL DEFAULT 'todo' CHECK (status IN ('needs_confirmation', 'todo', 'blocked',
                          'scheduled', 'in_progress', 'done', 'missed', 'dropped')),
    times_missed        int NOT NULL DEFAULT 0,
    confidence          real NOT NULL DEFAULT 1.0,
    needs_confirmation  boolean NOT NULL DEFAULT false,
    history             jsonb NOT NULL DEFAULT '[]',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tasks_status ON tasks (status);
CREATE INDEX tasks_due ON tasks (due_at);

CREATE TABLE meeting_requests (
    id                  text PRIMARY KEY,
    email_id            text REFERENCES emails(id),
    requester_entity_id text REFERENCES entities(id),
    proposed_start      timestamptz,
    proposed_end        timestamptz,
    time_text           text,
    timezone            text,
    topic               text,
    link                text,
    availability        jsonb,
    status              text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'checked', 'held', 'awaiting_approval',
                          'accepted', 'declined', 'counter_proposed', 'expired')),
    held_event_id       text,
    reply_email_id      text REFERENCES emails(id),
    correlation_id      text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calendar_events (
    id                  text PRIMARY KEY,
    title               text NOT NULL,
    starts_at           timestamptz NOT NULL,
    ends_at             timestamptz NOT NULL,
    kind                text NOT NULL DEFAULT 'meeting' CHECK (kind IN ('meeting', 'focus', 'personal', 'travel',
                          'hold', 'task')),
    flexible            boolean NOT NULL DEFAULT true,    -- can the Planner move it? (gym = no)
    task_id             text REFERENCES tasks(id),
    meeting_request_id  text REFERENCES meeting_requests(id),
    location            text,
    attendees           text[] NOT NULL DEFAULT '{}',
    external_uid        text UNIQUE,                      -- iCalendar UID when imported
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at)
);
CREATE INDEX calendar_events_start ON calendar_events (starts_at);
ALTER TABLE meeting_requests ADD FOREIGN KEY (held_event_id) REFERENCES calendar_events(id);

CREATE TABLE plans (
    id                  text PRIMARY KEY,
    plan_date           date NOT NULL,
    version             int NOT NULL,
    reason              text NOT NULL DEFAULT '',
    created_by          text NOT NULL DEFAULT 'planner',
    approved            boolean NOT NULL DEFAULT false,
    approved_via        text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (plan_date, version)
);

CREATE TABLE plan_items (
    id                  text PRIMARY KEY,
    plan_id             text NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_id             text REFERENCES tasks(id),
    event_id            text REFERENCES calendar_events(id),
    starts_at           timestamptz NOT NULL,
    ends_at             timestamptz NOT NULL,
    position            int NOT NULL,
    CHECK (task_id IS NOT NULL OR event_id IS NOT NULL)
);

-- ===================================================================================== MEMORY

CREATE TABLE promises (
    id                  text PRIMARY KEY,
    promiser            text NOT NULL,                -- 'me' or entity id
    promisee            text NOT NULL,
    what                text NOT NULL,
    due_at              timestamptz,
    source_id           text REFERENCES sources(id),
    evidence_quote      text NOT NULL DEFAULT '',
    evidence_source_id  text REFERENCES sources(id),  -- proof it was done
    status              text NOT NULL DEFAULT 'detected' CHECK (status IN ('detected', 'confirmed', 'tracking',
                          'done', 'overdue', 'escalated', 'broken')),
    reminders_sent      int NOT NULL DEFAULT 0,
    correlation_id      text,
    history             jsonb NOT NULL DEFAULT '[]',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX promises_status ON promises (status);

CREATE TABLE decisions (
    id                     text PRIMARY KEY,
    what                   text NOT NULL,
    why                    text NOT NULL DEFAULT '',
    alternatives_rejected  text[] NOT NULL DEFAULT '{}',
    decided_by             text,
    decided_at             timestamptz,
    revisit_at             timestamptz,
    replaced_by            text REFERENCES decisions(id),
    source_id              text REFERENCES sources(id),
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lessons (
    id            text PRIMARY KEY,
    what          text NOT NULL,
    applies_to    text NOT NULL DEFAULT '',
    source_id     text REFERENCES sources(id),
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- ===================================================================================== AGENTS

CREATE TABLE events (
    id               text PRIMARY KEY,
    type             text NOT NULL,
    version          int NOT NULL DEFAULT 1,
    occurred_at      timestamptz NOT NULL,           -- demo clock
    recorded_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    emitted_by       text NOT NULL,
    idempotency_key  text NOT NULL UNIQUE,
    correlation_id   text,
    caused_by        text REFERENCES events(id),
    subject_kind     text,
    subject_id       text,
    priority         text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    payload          jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX events_type ON events (type);
CREATE INDEX events_correlation ON events (correlation_id);

-- One row per (event, consumer): makes delivery safe to retry and duplicates harmless.
CREATE TABLE event_deliveries (
    event_id     text NOT NULL REFERENCES events(id),
    consumer     text NOT NULL,
    status       text NOT NULL CHECK (status IN ('processing', 'done', 'failed')),
    attempts     int NOT NULL DEFAULT 1,
    last_error   text,
    updated_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (event_id, consumer)
);

CREATE TABLE board_messages (
    id              text PRIMARY KEY,
    from_agent      text NOT NULL,
    to_agent        text,
    correlation_id  text,
    text            text NOT NULL,
    refs            jsonb NOT NULL DEFAULT '{}',
    at              timestamptz NOT NULL,           -- demo clock
    recorded_at     timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX board_messages_correlation ON board_messages (correlation_id);

CREATE TABLE agent_runs (
    id                text PRIMARY KEY,
    agent             text NOT NULL,
    trigger_event_id  text REFERENCES events(id),
    correlation_id    text,
    model             text,
    started_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at       timestamptz,
    duration_ms       int,
    input_tokens      int NOT NULL DEFAULT 0,
    output_tokens     int NOT NULL DEFAULT 0,
    status            text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'retried', 'failed')),
    error             text
);

-- ==================================================================================== CONTROL

CREATE TABLE permissions (
    agent    text NOT NULL,
    tool     text NOT NULL,                        -- "email.send_email"
    risk     text NOT NULL CHECK (risk IN ('green', 'yellow', 'red')),
    allowed  boolean NOT NULL DEFAULT true,
    PRIMARY KEY (agent, tool)
);

CREATE TABLE policies (
    id            text PRIMARY KEY,
    rule_text     text NOT NULL,                   -- "Never share salary data outside the company"
    check_kind    text NOT NULL,                   -- which built-in check enforces it
    check_config  jsonb NOT NULL DEFAULT '{}',
    enabled       boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tool_calls (
    id              text PRIMARY KEY,
    agent           text NOT NULL,
    tool            text NOT NULL,
    input           jsonb NOT NULL DEFAULT '{}',
    risk            text NOT NULL CHECK (risk IN ('green', 'yellow', 'red')),
    decision        text NOT NULL CHECK (decision IN ('allowed', 'blocked', 'pending_approval', 'approved',
                      'rejected', 'expired')),
    reason          text,
    approval_id     text,
    result          jsonb,
    error           text,
    correlation_id  text,
    called_at       timestamptz NOT NULL,           -- demo clock
    finished_at     timestamptz
);
CREATE INDEX tool_calls_correlation ON tool_calls (correlation_id);

CREATE TABLE approvals (
    id                  text PRIMARY KEY,
    tool_call_id        text NOT NULL REFERENCES tool_calls(id),
    requested_by_agent  text NOT NULL,
    action              text NOT NULL,
    risk                text NOT NULL CHECK (risk IN ('green', 'yellow', 'red')),
    title               text NOT NULL,
    summary             text NOT NULL,
    preview             text,
    buttons             text[] NOT NULL DEFAULT '{approve,reject}',
    token_hash          text NOT NULL,             -- sha256 of the one-time token; the token is never stored
    status              text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected',
                          'expired')),
    decided_via         text CHECK (decided_via IN ('watch', 'phone', 'dashboard')),
    decided_at          timestamptz,
    expires_at          timestamptz NOT NULL,
    correlation_id      text,
    created_at          timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE tool_calls ADD FOREIGN KEY (approval_id) REFERENCES approvals(id);

CREATE TABLE settings (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
