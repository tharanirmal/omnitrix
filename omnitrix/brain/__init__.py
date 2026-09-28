"""The brain: ingestion of user-owned data into Postgres + pgvector, entity linking, and scoped recall.

Agents never read the whole dataset. They call `Brain.recall()`, which works out which people,
organizations and projects a question is about, narrows the search to the documents linked to them,
runs meaning + keyword search inside that scope, adds a few structured facts from the graph, and
returns a small context pack under a token budget.
"""
