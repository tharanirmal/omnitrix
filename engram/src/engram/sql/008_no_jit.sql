-- The brain's queries are millisecond lookups; compiling them just-in-time costs more (~15 ms) than it saves.
DO $$ BEGIN EXECUTE format('ALTER DATABASE %I SET jit = off', current_database()); END $$;
