# Project Memory Starter

Use this template when a project needs durable agent memory without requiring a database, vector index, or graph service. Copy this directory into the adopting project as `.agent-memory/` and commit the records that describe durable project knowledge. The included `.gitignore` excludes `.agent-memory/local/`, where machine-local indexes, caches, credentials, and private retrieval artifacts belong.

## Layout

```text
.agent-memory/
  records/
    <record-id>.md
  local/
```

Keep one durable fact, decision, handoff, or research result per record. Store generated indexes only in `local/`; the Markdown records remain the portable source of truth.

## Record Contract

Start every record from `record-template.md`. Record IDs must be stable and unique, such as `decision-auth-session-20260726` or `fact-api-rate-limit-20260726`.

Every material claim needs at least one primary source reference. For repository evidence, use a file path plus symbol or line range and the commit SHA or explicit dirty-worktree state. For commands and tests, preserve the full command, working directory, relevant input or environment versions, exit status, and observed result or durable output reference. For external evidence, use a URL and retrieval date. Mark summaries and inferences explicitly; they are not primary evidence. A search, vector, or graph retrieval result may locate a claim, but cannot be its only source.

Relationships have globally unique, stable IDs, target record IDs, and simple predicates such as `supersedes`, `supports`, `contradicts`, `implements`, or `depends-on`. Prefix each relation ID with its source record ID, for example `decision-auth-session-20260726--supports--fact-session-security-20260726`. This makes the records graph-ready without requiring a graph database.

## Retrieval Contract

Any full-text, vector, or graph retrieval tool must return the same evidence needed by the Context Integrity Protocol:

- record IDs and relationship IDs when applicable
- primary source references, retrieval query, and retrieval mode
- retrieval time, freshness limits, access limits, conflicts, omissions, and failures
- the exact claims returned, with confidence and whether each is fact, summary, or inference
- omitted scopes, conflicts, and retrieval failures

Agents should read the primary records for material claims. A retrieval result narrows the search; it does not replace evidence verification or primary sources.

## Adoption Stages

1. **Files only**: Read records directly and link them in handoffs. Use this for new or small projects.
2. **SQLite FTS5 index**: Offer the local SQLite option in [sqlite](sqlite) when record volume makes direct reading slow. It is the recommended local index, but remains optional; keep records authoritative.
3. **Semantic retrieval**: Add embeddings or a vector store when vocabulary mismatch prevents reliable keyword retrieval. Return record IDs and source links with every result.
4. **Graph retrieval**: Add a graph store when multi-hop relationships, dependency impact analysis, or entity-centric questions are recurring needs. Derive nodes and edges from the same record IDs and relationships; do not make the graph the only source of provenance.

Do not advance stages because the technology is available. Advance when the current stage cannot answer recurring questions accurately, quickly, or with sufficient provenance.