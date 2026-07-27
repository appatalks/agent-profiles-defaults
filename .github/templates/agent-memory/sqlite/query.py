#!/usr/bin/env python3
"""Query a local SQLite FTS memory index and emit a Context Integrity packet."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def query_database(database_path: Path, query: str, limit: int) -> dict[str, object]:
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT records.id, records.path, records.title, records.kind, records.status,
                   records.confidence, records.indexed_at,
                   snippet(records_fts, 2, '[', ']', '...', 24) AS excerpt
            FROM records_fts
            JOIN records ON records.rowid = records_fts.rowid
            WHERE records_fts MATCH ?
            ORDER BY bm25(records_fts)
            LIMIT ?
            """,
            (query, limit + 1),
        ).fetchall()
        truncated = len(rows) > limit
        rows = rows[:limit]
        record_ids = [row["id"] for row in rows]
        if record_ids:
            placeholders = ", ".join("?" for _ in record_ids)
            relations = connection.execute(
                f"""
                SELECT id, predicate FROM relations
                WHERE source_record_id IN ({placeholders}) OR target_record_id IN ({placeholders})
                """,
                record_ids * 2,
            ).fetchall()
            sources = connection.execute(
                f"""
                SELECT record_id, id, type, reference, retrieved_at, freshness, revision, execution_json
                FROM sources WHERE record_id IN ({placeholders})
                """,
                record_ids,
            ).fetchall()
            claims = connection.execute(
                f"""
                SELECT record_id, ordinal, classification, text, confidence, primary_source_id, retrieval_id
                FROM claims WHERE record_id IN ({placeholders}) ORDER BY record_id, ordinal
                """,
                record_ids,
            ).fetchall()
            prior_retrievals = connection.execute(
                f"""
                SELECT record_id, id, mode, query, retrieved_at, record_ids_json,
                       relation_ids_json, freshness, limitations
                FROM retrievals WHERE record_id IN ({placeholders})
                """,
                record_ids,
            ).fetchall()
        else:
            relations = []
            sources = []
            claims = []
            prior_retrievals = []
    primary_sources = []
    for source in sources:
        source_data = dict(source)
        source_data["execution"] = json.loads(source_data.pop("execution_json"))
        primary_sources.append(source_data)
    record_retrievals = []
    for retrieval in prior_retrievals:
        retrieval_data = dict(retrieval)
        retrieval_data["record_ids"] = json.loads(retrieval_data.pop("record_ids_json"))
        retrieval_data["relation_ids"] = json.loads(retrieval_data.pop("relation_ids_json"))
        record_retrievals.append(retrieval_data)
    return {
        "mode": "full-text",
        "query": query,
        "retrieved_at": retrieved_at,
        "record_ids": record_ids,
        "relation_ids": [row["id"] for row in relations],
        "primary_sources": primary_sources,
        "claims": [dict(row) for row in claims],
        "candidate_records": [dict(row) for row in rows],
        "record_retrievals": record_retrievals,
        "freshness": "Index freshness is recorded per candidate record in indexed_at.",
        "access_limits": ["SQLite does not encode source permissions or external access controls."],
        "conflicts": [
            {"relation_id": row["id"], "reason": "A returned relation is marked as contradicts."}
            for row in relations if row["predicate"] == "contradicts"
        ],
        "limit": limit,
        "omissions": [
            "Unsynchronized records and source content outside the local Markdown records are not searched.",
            *([f"Results were truncated at the requested limit of {limit}."] if truncated else []),
        ],
        "failures": [],
        "limitations": [
            "SQLite FTS5 performs lexical retrieval only.",
            "Candidate records and claims require verification against the referenced Markdown records and primary sources.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="SQLite FTS5 query syntax")
    parser.add_argument("--database", type=Path, default=Path(".agent-memory/local/memory.db"))
    parser.add_argument("--limit", type=int, default=10)
    arguments = parser.parse_args()
    if arguments.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if not arguments.database.is_file():
        raise SystemExit(f"Memory database does not exist: {arguments.database}. Run sync.py first.")
    try:
        print(json.dumps(query_database(arguments.database, arguments.query, arguments.limit), indent=2))
    except sqlite3.Error as error:
        raise SystemExit(f"Memory query failed: {error}") from error


if __name__ == "__main__":
    main()