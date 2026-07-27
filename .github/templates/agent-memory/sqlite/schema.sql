PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cache_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('cache_kind', 'agent-memory-sqlite');

CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  tags TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
  id TEXT PRIMARY KEY,
  source_record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  predicate TEXT NOT NULL,
  target_record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS relations_source_record_id_index ON relations(source_record_id);
CREATE INDEX IF NOT EXISTS relations_target_record_id_index ON relations(target_record_id);

CREATE TABLE IF NOT EXISTS sources (
  record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  id TEXT NOT NULL,
  type TEXT NOT NULL,
  reference TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  freshness TEXT NOT NULL,
  revision TEXT NOT NULL,
  execution_json TEXT NOT NULL,
  PRIMARY KEY (record_id, id)
);

CREATE TABLE IF NOT EXISTS retrievals (
  record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  id TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('direct', 'full-text', 'vector', 'graph')),
  query TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  record_ids_json TEXT NOT NULL,
  relation_ids_json TEXT NOT NULL,
  freshness TEXT NOT NULL,
  limitations TEXT NOT NULL,
  PRIMARY KEY (record_id, id)
);

CREATE TABLE IF NOT EXISTS claims (
  record_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  classification TEXT NOT NULL CHECK (classification IN ('Fact', 'Summary', 'Inference')),
  text TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  primary_source_id TEXT NOT NULL,
  retrieval_id TEXT,
  PRIMARY KEY (record_id, ordinal),
  FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
  FOREIGN KEY (record_id, primary_source_id) REFERENCES sources(record_id, id),
  FOREIGN KEY (record_id, retrieval_id) REFERENCES retrievals(record_id, id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  id UNINDEXED,
  title,
  body,
  tags,
  content = 'records',
  content_rowid = 'rowid'
);

CREATE TRIGGER IF NOT EXISTS records_after_insert AFTER INSERT ON records BEGIN
  INSERT INTO records_fts(rowid, id, title, body, tags)
  VALUES (new.rowid, new.id, new.title, new.body, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS records_after_delete AFTER DELETE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, id, title, body, tags)
  VALUES ('delete', old.rowid, old.id, old.title, old.body, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS records_after_update AFTER UPDATE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, id, title, body, tags)
  VALUES ('delete', old.rowid, old.id, old.title, old.body, old.tags);
  INSERT INTO records_fts(rowid, id, title, body, tags)
  VALUES (new.rowid, new.id, new.title, new.body, new.tags);
END;

PRAGMA user_version = 3;