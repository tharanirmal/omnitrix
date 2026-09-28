-- BM25 for keyword search. Postgres full-text ranking has no inverse document frequency, so a word in every
-- email ("vince") counts as much as a rare name; measured on EnronQA, that made keyword search the weak half of
-- hybrid retrieval. These two views give BM25 its corpus statistics; `engram index` refreshes them.

CREATE MATERIALIZED VIEW chunk_stats AS
SELECT count(*)::float8 AS n, greatest(avg(length(tsv)), 1)::float8 AS avgdl FROM chunks;

CREATE MATERIALIZED VIEW lexeme_idf AS
SELECT word AS lexeme, ndoc AS df, ln(1 + ((SELECT n FROM chunk_stats) - ndoc + 0.5) / (ndoc + 0.5)) AS idf
FROM ts_stat('SELECT tsv FROM public.chunks');   -- schema-qualified: PG17 builds views with a locked search_path
CREATE UNIQUE INDEX lexeme_idf_lexeme ON lexeme_idf (lexeme);
