-- A login for the page's SQL console that can only read: not a superuser, so no COPY TO PROGRAM, no server files,
-- no signalling other sessions. (A read-only transaction alone does not stop those.) Roles are per server, grants
-- per database. Local-only credentials: the server listens on 127.0.0.1.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'engram_reader') THEN
    CREATE ROLE engram_reader LOGIN PASSWORD 'engram_reader' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO engram_reader', current_database());
END $$;
GRANT USAGE ON SCHEMA public TO engram_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO engram_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO engram_reader;
