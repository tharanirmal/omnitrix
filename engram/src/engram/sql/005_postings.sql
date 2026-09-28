-- BM25 from an inverted index (LR §4.4). One row per (word, chunk) with the word's count and the chunk's length,
-- so a query reads only the postings of its own words, instead of unnesting the whole vector of every chunk that
-- contains any of them. Document length is now the chunk's word count, as in textbook BM25 (it was its number of
-- distinct words). Rebuilt with the other statistics by index.refresh_stats() after the chunks change.
DROP MATERIALIZED VIEW lexeme_idf;
DROP MATERIALIZED VIEW chunk_stats;

CREATE MATERIALIZED VIEW postings AS
SELECT t.lexeme, c.id AS chunk_id, cardinality(t.positions) AS tf,
       sum(cardinality(t.positions)) OVER (PARTITION BY c.id)::int AS len
FROM public.chunks c, unnest(c.tsv) t;
CREATE INDEX postings_lexeme ON postings (lexeme) INCLUDE (chunk_id, tf, len);

CREATE MATERIALIZED VIEW chunk_stats AS
SELECT (SELECT count(*) FROM public.chunks)::float8 AS n,
       greatest((SELECT avg(len) FROM (SELECT DISTINCT chunk_id, len FROM public.postings) d), 1)::float8 AS avgdl;

CREATE MATERIALIZED VIEW lexeme_idf AS
SELECT lexeme, count(*) AS df, ln(1 + ((SELECT n FROM public.chunk_stats) - count(*) + 0.5) / (count(*) + 0.5)) AS idf
FROM public.postings GROUP BY lexeme;
CREATE UNIQUE INDEX lexeme_idf_lexeme ON lexeme_idf (lexeme);
