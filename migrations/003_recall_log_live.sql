-- Agent log for the dashboard: newest-first listing, filtering by agent, and a live feed.

CREATE INDEX recall_log_at ON recall_log (at DESC, recorded_at DESC);
CREATE INDEX recall_log_agent ON recall_log (agent);

-- Every new recall is announced on 'omnitrix_recall' with its id, whoever wrote it (the CLI, the benchmark,
-- any agent), so the dashboard updates without polling. The NOTIFY goes out when the transaction commits.
CREATE FUNCTION recall_log_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('omnitrix_recall', NEW.id);
    RETURN NEW;
END $$;

CREATE TRIGGER recall_log_notify AFTER INSERT ON recall_log
    FOR EACH ROW EXECUTE FUNCTION recall_log_notify();
