# Optional SQLite Memory Index

Choose this option when a project has enough durable memory records that direct reading is slow, but does not yet need semantic or multi-hop graph retrieval. It uses SQLite FTS5 for local full-text search. SQLite is the recommended default index because it is embedded, versionable as a schema, portable across project stacks, and has no server to operate.

The database is an ignored, derived cache. Markdown records in `.agent-memory/records/` remain authoritative. The sync tool checks the schema version and rebuilds incompatible caches. Delete and rebuild the database whenever the index is suspect.

## Setup

1. Ensure Python 3.10 or later, SQLite with FTS5, and PyYAML are available:

   ```bash
   python3 -m pip install PyYAML
   python3 -c "import sqlite3; connection = sqlite3.connect(':memory:'); connection.execute('CREATE VIRTUAL TABLE check_fts USING fts5(content)')"
   ```

2. Synchronize the records:

   ```bash
   python3 .agent-memory/sqlite/sync.py
   ```

3. Query the index:

   ```bash
   python3 .agent-memory/sqlite/query.py "authentication"
   ```

Run `sync.py` after record changes. The query tool emits a JSON Context Integrity retrieval packet with candidate records, exact stored claims, record and relation IDs, complete primary-source metadata, prior retrieval metadata, retrieval time, freshness context, access limits, conflicts, omissions, failures, and limitations. Results remain candidates until an agent verifies the referenced Markdown record and primary evidence.

## When To Choose Something Else

- Use files only when direct record reading is fast and reliable.
- Add vectors only for demonstrated vocabulary mismatch; keep SQLite metadata and provenance as the stable local catalog.
- Add a graph store only for recurring multi-hop or entity-centric queries; derive it from record and relation IDs instead of making it authoritative.

Do not store secrets, raw private prompts, or unreviewed conversational transcripts in the database. The database inherits the sensitivity of the records it indexes. The sync tool creates the local directory with owner-only permissions and the database with mode `0600`; preserve those restrictions when copying or backing up the cache.