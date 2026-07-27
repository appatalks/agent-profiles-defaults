#!/usr/bin/env python3
"""Synchronize authoritative Markdown memory records into a local SQLite index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError as error:
    raise SystemExit("PyYAML is required: python3 -m pip install PyYAML") from error


CACHE_VERSION = 3
RECORD_KINDS = {"fact", "decision", "handoff", "research"}
RECORD_STATUSES = {"active", "superseded", "disputed"}
RELATION_PREDICATES = {"supports", "contradicts", "supersedes", "implements", "depends-on"}
SOURCE_TYPES = {"repository", "test", "command", "url"}
RETRIEVAL_MODES = {"direct", "full-text", "vector", "graph"}
CLAIM_PATTERN = re.compile(
    r"- \*\*(Fact|Summary|Inference)\*\*: (.+?) "
    r"\(primary source: `([^`]+)`; retrieval: `([^`]+)`; confidence: (\d{1,3})\)$",
)


def require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def normalize_date(value: object, field: str) -> str:
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be an ISO-8601 date without a time")
    if isinstance(value, date):
        return value.isoformat()
    text = require_string(value, field)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 date") from error


def normalize_timestamp(value: object, field: str) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value.tzinfo else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = require_string(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            date.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"{field} must be an ISO-8601 date or timestamp") from error
    return text


def require_confidence(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError(f"{field} must be an integer from 0 to 100")
    return value


def validate_execution(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("source execution must be a mapping")
    string_fields = ("command", "cwd", "inputs", "result")
    for field in string_fields:
        require_string(value.get(field), f"source execution {field}")
    exit_status = value.get("exit_status")
    if isinstance(exit_status, bool) or not isinstance(exit_status, (int, str)):
        raise ValueError("source execution exit_status must be an integer or non-empty string")
    if isinstance(exit_status, str) and not exit_status.strip():
        raise ValueError("source execution exit_status must be an integer or non-empty string")
    if isinstance(exit_status, int) and exit_status < 0:
        raise ValueError("source execution exit_status cannot be negative")
    return value


def parse_record(path: Path, memory_root: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)(.*)\Z", content, re.DOTALL)
    if not frontmatter_match:
        raise ValueError("record must use line-delimited YAML frontmatter markers")
    frontmatter, body = frontmatter_match.groups()
    try:
        metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError as error:
        raise ValueError("record frontmatter must contain valid YAML") from error
    if not isinstance(metadata, dict):
        raise ValueError("record frontmatter must be a mapping")
    title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), None)
    if not title:
        raise ValueError("record must contain a level-one title")
    required_fields = ("id", "kind", "status", "confidence", "created", "updated")
    missing_fields = [field for field in required_fields if field not in metadata]
    if missing_fields:
        raise ValueError(f"record is missing required fields: {', '.join(missing_fields)}")
    record_id = require_string(metadata["id"], "id")
    kind = require_string(metadata["kind"], "kind")
    status = require_string(metadata["status"], "status")
    if kind not in RECORD_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(RECORD_KINDS))}")
    if status not in RECORD_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(RECORD_STATUSES))}")
    tags = require_list(metadata.get("tags", []), "tags")
    if not all(isinstance(tag, str) and tag.strip() for tag in tags):
        raise ValueError("tags must contain only non-empty strings")
    relations = require_list(metadata.get("relations", []), "relations")
    validated_relations: list[dict[str, str]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            raise ValueError("each relation must be a mapping")
        relation_id = require_string(relation.get("id"), "relation id")
        predicate = require_string(relation.get("predicate"), "relation predicate")
        if predicate not in RELATION_PREDICATES:
            raise ValueError(f"relation predicate must be one of: {', '.join(sorted(RELATION_PREDICATES))}")
        validated_relations.append({
            "id": relation_id,
            "predicate": predicate,
            "target": require_string(relation.get("target"), "relation target"),
        })
    sources = require_list(metadata.get("sources"), "sources")
    if not sources:
        raise ValueError("records must contain at least one primary source")
    validated_sources: list[dict[str, object]] = []
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each source must be a mapping")
        source_id = require_string(source.get("id"), "source id")
        if source_id in source_ids:
            raise ValueError(f"source IDs must be unique within a record: {source_id}")
        source_ids.add(source_id)
        source_type = require_string(source.get("type"), "source type")
        if source_type not in SOURCE_TYPES:
            raise ValueError(f"source type must be one of: {', '.join(sorted(SOURCE_TYPES))}")
        execution = validate_execution(source.get("execution"))
        validated_sources.append({
            "id": source_id,
            "type": source_type,
            "reference": require_string(source.get("reference"), "source reference"),
            "retrieved": normalize_timestamp(source.get("retrieved"), "source retrieved"),
            "freshness": require_string(source.get("freshness"), "source freshness"),
            "revision": require_string(source.get("revision"), "source revision"),
            "execution": execution,
        })
    retrievals = require_list(metadata.get("retrieval", []), "retrieval")
    validated_retrievals: list[dict[str, object]] = []
    retrieval_ids: set[str] = set()
    for retrieval in retrievals:
        if not isinstance(retrieval, dict):
            raise ValueError("each retrieval must be a mapping")
        retrieval_id = require_string(retrieval.get("id"), "retrieval id")
        if retrieval_id == "none":
            raise ValueError("retrieval id 'none' is reserved for claims without a retrieval")
        if retrieval_id in retrieval_ids:
            raise ValueError(f"retrieval IDs must be unique within a record: {retrieval_id}")
        retrieval_ids.add(retrieval_id)
        mode = require_string(retrieval.get("mode"), "retrieval mode")
        if mode not in RETRIEVAL_MODES:
            raise ValueError(f"retrieval mode must be one of: {', '.join(sorted(RETRIEVAL_MODES))}")
        record_ids = require_list(retrieval.get("record_ids"), "retrieval record_ids")
        relation_ids = require_list(retrieval.get("relation_ids"), "retrieval relation_ids")
        if not all(isinstance(item, str) and item.strip() for item in record_ids + relation_ids):
            raise ValueError("retrieval record_ids and relation_ids must contain only non-empty strings")
        validated_retrievals.append({
            "id": retrieval_id,
            "mode": mode,
            "query": require_string(retrieval.get("query"), "retrieval query"),
            "retrieved": normalize_timestamp(retrieval.get("retrieved"), "retrieval retrieved"),
            "record_ids": record_ids,
            "relation_ids": relation_ids,
            "freshness": require_string(retrieval.get("freshness"), "retrieval freshness"),
            "limitations": require_string(retrieval.get("limitations"), "retrieval limitations"),
        })
    claims_section = re.search(r"^## Claims\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if not claims_section:
        raise ValueError("record must contain a Claims section")
    claim_lines = [line for line in claims_section.group(1).splitlines() if line.startswith("- ")]
    if not claim_lines:
        raise ValueError("record must contain at least one claim")
    claims = []
    for ordinal, line in enumerate(claim_lines, start=1):
        match = CLAIM_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("each claim must use the record-template claim format")
        classification, text, source_id, retrieval_id, confidence = match.groups()
        if source_id not in source_ids:
            raise ValueError(f"claim references an unknown primary source: {source_id}")
        if retrieval_id != "none" and retrieval_id not in retrieval_ids:
            raise ValueError(f"claim references an unknown retrieval: {retrieval_id}")
        claims.append({
            "ordinal": ordinal,
            "classification": classification,
            "text": text,
            "confidence": require_confidence(int(confidence), "claim confidence"),
            "primary_source_id": source_id,
            "retrieval_id": None if retrieval_id == "none" else retrieval_id,
        })
    return {
        "id": record_id,
        "path": str(path.relative_to(memory_root)),
        "kind": kind,
        "status": status,
        "title": title,
        "body": body.strip(),
        "confidence": require_confidence(metadata["confidence"], "confidence"),
        "tags": json.dumps(tags, sort_keys=True),
        "created_at": normalize_date(metadata["created"], "created"),
        "updated_at": normalize_date(metadata["updated"], "updated"),
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "relations": validated_relations,
        "sources": validated_sources,
        "retrievals": validated_retrievals,
        "claims": claims,
    }


def validate_cross_record_references(records: list[dict[str, object]]) -> None:
    record_ids = [record["id"] for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("record IDs must be unique")
    relation_ids: set[str] = set()
    for record in records:
        for relation in record["relations"]:
            relation_id = relation["id"]
            if relation_id in relation_ids:
                raise ValueError(f"relationship IDs must be globally unique: {relation_id}")
            if relation["target"] not in record_ids:
                raise ValueError(f"relationship target does not exist: {relation['target']}")
            relation_ids.add(relation_id)


def initialize_database(connection: sqlite3.Connection, schema_path: Path, allow_unrecognized_rebuild: bool) -> None:
    objects = connection.execute(
        "SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tables = {name for name, object_type in objects if object_type == "table"}
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    cache_kind = None
    if "cache_metadata" in tables:
        try:
            cache_kind = connection.execute(
                "SELECT value FROM cache_metadata WHERE key = 'cache_kind'"
            ).fetchone()
            cache_kind = cache_kind[0] if cache_kind else None
        except sqlite3.DatabaseError:
            cache_kind = None
    requires_rebuild = version != CACHE_VERSION or cache_kind != "agent-memory-sqlite"
    if requires_rebuild and objects:
        if not allow_unrecognized_rebuild and cache_kind != "agent-memory-sqlite":
            raise sqlite3.DatabaseError("refusing to rebuild an unrecognized custom SQLite database")
        connection.execute("PRAGMA foreign_keys = OFF")
        for name, object_type in sorted(objects, key=lambda item: item[1] != "trigger"):
            quoted_name = name.replace('"', '""')
            if object_type == "trigger":
                connection.execute(f'DROP TRIGGER IF EXISTS "{quoted_name}"')
            elif object_type == "view":
                connection.execute(f'DROP VIEW IF EXISTS "{quoted_name}"')
            elif object_type == "table":
                connection.execute(f'DROP TABLE IF EXISTS "{quoted_name}"')
        connection.execute("PRAGMA user_version = 0")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    if connection.execute("PRAGMA user_version").fetchone()[0] != CACHE_VERSION:
        raise sqlite3.DatabaseError("SQLite memory schema version did not initialize correctly")


def synchronize(memory_root: Path, database_path: Path, schema_path: Path) -> int:
    records_path = memory_root / "records"
    if not records_path.is_dir():
        raise ValueError(f"records directory does not exist: {records_path}")
    parsed_records = [parse_record(path, memory_root) for path in sorted(records_path.glob("*.md"))]
    validate_cross_record_references(parsed_records)
    record_ids = [record["id"] for record in parsed_records]
    default_database_path = memory_root / "local" / "memory.db"
    is_default_database = database_path == default_database_path
    if is_default_database and (database_path.is_symlink() or default_database_path.parent.is_symlink()):
        raise ValueError("default SQLite cache path and local directory must not be symlinks")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if is_default_database:
        os.chmod(database_path.parent, 0o700)
    database_path.touch(exist_ok=True)
    os.chmod(database_path, 0o600)
    indexed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(database_path) as connection:
        initialize_database(connection, schema_path, is_default_database)
        connection.execute("BEGIN")
        for record in parsed_records:
            connection.execute(
                """
                INSERT INTO records (
                  id, path, kind, status, title, body, confidence, tags,
                  created_at, updated_at, content_hash, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  path = excluded.path, kind = excluded.kind, status = excluded.status,
                  title = excluded.title, body = excluded.body, confidence = excluded.confidence,
                  tags = excluded.tags, created_at = excluded.created_at,
                  updated_at = excluded.updated_at, content_hash = excluded.content_hash,
                  indexed_at = excluded.indexed_at
                """,
                (
                    record["id"], record["path"], record["kind"], record["status"],
                    record["title"], record["body"], record["confidence"], record["tags"],
                    record["created_at"], record["updated_at"], record["content_hash"], indexed_at,
                ),
            )
        if record_ids:
            placeholders = ", ".join("?" for _ in record_ids)
            connection.execute(f"DELETE FROM records WHERE id NOT IN ({placeholders})", record_ids)
        else:
            connection.execute("DELETE FROM records")
        connection.execute("DELETE FROM claims")
        connection.execute("DELETE FROM retrievals")
        connection.execute("DELETE FROM relations")
        connection.execute("DELETE FROM sources")
        for record in parsed_records:
            for source in record["sources"]:
                connection.execute(
                    """
                    INSERT INTO sources (
                      record_id, id, type, reference, retrieved_at, freshness, revision, execution_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], source["id"], source["type"], source["reference"],
                        source["retrieved"], source["freshness"], source["revision"],
                        json.dumps(source.get("execution", {}), sort_keys=True),
                    ),
                )
            for retrieval in record["retrievals"]:
                connection.execute(
                    """
                    INSERT INTO retrievals (
                      record_id, id, mode, query, retrieved_at, record_ids_json,
                      relation_ids_json, freshness, limitations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], retrieval["id"], retrieval["mode"], retrieval["query"],
                        retrieval["retrieved"], json.dumps(retrieval["record_ids"]),
                        json.dumps(retrieval["relation_ids"]), retrieval["freshness"], retrieval["limitations"],
                    ),
                )
            for claim in record["claims"]:
                connection.execute(
                    """
                    INSERT INTO claims (
                      record_id, ordinal, classification, text, confidence, primary_source_id, retrieval_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], claim["ordinal"], claim["classification"], claim["text"],
                        claim["confidence"], claim["primary_source_id"], claim["retrieval_id"],
                    ),
                )
            for relation in record["relations"]:
                connection.execute(
                    "INSERT INTO relations (id, source_record_id, predicate, target_record_id) VALUES (?, ?, ?, ?)",
                    (relation["id"], record["id"], relation["predicate"], relation["target"]),
                )
    return len(parsed_records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-root", type=Path, default=Path(".agent-memory"))
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("schema.sql"))
    arguments = parser.parse_args()
    database_path = arguments.database or arguments.memory_root / "local" / "memory.db"
    try:
        count = synchronize(arguments.memory_root, database_path, arguments.schema)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Memory synchronization failed: {error}") from error
    print(f"Indexed {count} record(s) in {database_path}")


if __name__ == "__main__":
    main()