-- Postings as a table maintained per new chunk (round2-plan.md §C.6): adding an item no longer recomputes the
-- whole inverted index. Corpus statistics (document frequencies, average length) stay materialized views that are
-- refreshed lazily — a few new documents barely move them.
DROP MATERIALIZED VIEW lexeme_idf;
DROP MATERIALIZED VIEW chunk_stats;
ALTER MATERIALIZED VIEW postings RENAME TO postings_old;
CREATE TABLE postings (
    lexeme    text   NOT NULL,
    chunk_id  bigint NOT NULL REFERENCES chunks (id) ON DELETE CASCADE,
    tf        int    NOT NULL,
    len       int    NOT NULL
);
INSERT INTO postings SELECT lexeme, chunk_id, tf, len FROM postings_old;
DROP MATERIALIZED VIEW postings_old;
CREATE INDEX postings_lexeme ON postings (lexeme) INCLUDE (chunk_id, tf, len);
CREATE INDEX postings_chunk ON postings (chunk_id);

CREATE MATERIALIZED VIEW chunk_stats AS
SELECT (SELECT count(*) FROM public.chunks)::float8 AS n,
       greatest((SELECT avg(len) FROM (SELECT DISTINCT chunk_id, len FROM public.postings) d), 1)::float8 AS avgdl;
CREATE MATERIALIZED VIEW lexeme_idf AS
SELECT lexeme, count(*) AS df, ln(1 + ((SELECT n FROM public.chunk_stats) - count(*) + 0.5) / (count(*) + 0.5)) AS idf
FROM public.postings GROUP BY lexeme;
CREATE UNIQUE INDEX lexeme_idf_lexeme ON lexeme_idf (lexeme);
