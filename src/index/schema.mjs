/**
 * Schema definition, connection setup, and how an index is opened or rebuilt.
 */

import { DatabaseSync } from 'node:sqlite';

import { BUSY_TIMEOUT_MS, assertDatabase, inTransaction, tableExists } from './internal.mjs';

/** Current shape of the derived index. */
export const SCHEMA_VERSION = 3;

const SCHEMA_VERSION_KEY = 'schema_version';

const REQUIRED_COLUMNS = {
  meta: ['key', 'value'],
  documents: ['path', 'kind', 'title', 'hash', 'indexed_at', 'parse_error'],
  work_items: [
    'row_id',
    'id',
    'document_path',
    'type',
    'status',
    'priority',
    'updated_at',
    'next_step',
    'approval_status',
    'clarification_summary',
  ],
  decisions: ['row_id', 'id', 'document_path', 'work_item_id', 'status', 'updated_at'],
  research_items: [
    'row_id',
    'id',
    'document_path',
    'work_item_id',
    'mode',
    'status',
    'question',
    'scope',
    'recency',
    'updated_at',
    'next_action',
    'confirmation',
  ],
  links: [
    'row_id',
    'document_path',
    'source_kind',
    'source_id',
    'relation',
    'target_kind',
    'target_id',
  ],
};

const CREATE_SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS documents (
    path TEXT PRIMARY KEY NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT '',
    indexed_at TEXT NOT NULL,
    parse_error TEXT
  );

  -- IDs intentionally are not UNIQUE.  Keeping duplicate IDs lets validate
  -- report a hand-edited Markdown mistake instead of silently hiding a file.
  CREATE TABLE IF NOT EXISTS work_items (
    row_id INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    document_path TEXT NOT NULL UNIQUE REFERENCES documents(path) ON DELETE CASCADE,
    type TEXT,
    status TEXT,
    priority TEXT,
    updated_at TEXT,
    next_step TEXT,
    approval_status TEXT,
    clarification_summary TEXT
  );

  CREATE TABLE IF NOT EXISTS decisions (
    row_id INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    document_path TEXT NOT NULL UNIQUE REFERENCES documents(path) ON DELETE CASCADE,
    work_item_id TEXT,
    status TEXT,
    updated_at TEXT
  );

  -- Research bodies and source notes remain in Markdown.  The index keeps
  -- only enough metadata to route a focused research agent to the right file.
  CREATE TABLE IF NOT EXISTS research_items (
    row_id INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    document_path TEXT NOT NULL UNIQUE REFERENCES documents(path) ON DELETE CASCADE,
    work_item_id TEXT,
    mode TEXT,
    status TEXT,
    question TEXT,
    scope TEXT,
    recency TEXT,
    updated_at TEXT,
    next_action TEXT,
    confirmation TEXT
  );

  -- Links are intentionally polymorphic.  A hard foreign key to a target
  -- would prevent validate from reporting a dangling Markdown reference.
  CREATE TABLE IF NOT EXISTS links (
    row_id INTEGER PRIMARY KEY,
    document_path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    UNIQUE (document_path, source_kind, source_id, relation, target_kind, target_id)
  );

  CREATE INDEX IF NOT EXISTS documents_kind_idx ON documents(kind);
  CREATE INDEX IF NOT EXISTS work_items_id_idx ON work_items(id);
  CREATE INDEX IF NOT EXISTS work_items_status_idx ON work_items(status);
  CREATE INDEX IF NOT EXISTS decisions_id_idx ON decisions(id);
  CREATE INDEX IF NOT EXISTS decisions_work_item_id_idx ON decisions(work_item_id);
  CREATE INDEX IF NOT EXISTS research_items_id_idx ON research_items(id);
  CREATE INDEX IF NOT EXISTS research_items_work_item_id_idx ON research_items(work_item_id);
  CREATE INDEX IF NOT EXISTS research_items_status_idx ON research_items(status);
  CREATE INDEX IF NOT EXISTS links_source_idx ON links(source_kind, source_id);
  CREATE INDEX IF NOT EXISTS links_target_idx ON links(target_kind, target_id);
`;

const DROP_SCHEMA_SQL = `
  DROP TABLE IF EXISTS links;
  DROP TABLE IF EXISTS research_items;
  DROP TABLE IF EXISTS decisions;
  DROP TABLE IF EXISTS work_items;
  DROP TABLE IF EXISTS documents;
  DROP TABLE IF EXISTS meta;
`;

/**
 * Open a project-local index and ensure that its schema is usable.
 *
 * `dbPath` is normally `<project>/.workflow/index.sqlite`.  Its parent
 * directory must already exist (the installer creates `.workflow/`).  Call
 * `db.close()` when a long-running caller is finished with the returned
 * native DatabaseSync instance.
 *
 * @param {string} dbPath
 * @returns {DatabaseSync}
 */
export function openIndex(dbPath) {
  if (typeof dbPath !== 'string' || dbPath.trim() === '') {
    throw new TypeError('dbPath must be a non-empty string.');
  }

  const db = new DatabaseSync(dbPath, {
    enableForeignKeyConstraints: true,
    timeout: BUSY_TIMEOUT_MS,
  });
  configureConnection(db);
  createSchema(db);
  return db;
}

/**
 * Open an existing index for querying only.
 *
 * Unlike `openIndex`, this never creates or migrates the schema, so callers do
 * not need the project write lock and any number of them may run concurrently
 * against the same WAL database.  The caller must ensure `dbPath` exists;
 * an absent or stale schema raises `WORKFLOW_INDEX_UNAVAILABLE`.
 *
 * @param {string} dbPath
 * @returns {DatabaseSync}
 */
export function openIndexForRead(dbPath) {
  if (typeof dbPath !== 'string' || dbPath.trim() === '') {
    throw new TypeError('dbPath must be a non-empty string.');
  }

  const db = new DatabaseSync(dbPath, {
    enableForeignKeyConstraints: true,
    timeout: BUSY_TIMEOUT_MS,
  });
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(`PRAGMA busy_timeout = ${BUSY_TIMEOUT_MS};`);
  if (!schemaIsCompatible(db)) {
    db.close();
    const unavailable = new Error('本地索引缺失或已过期：请先运行 workflow-os sync。');
    unavailable.code = 'WORKFLOW_INDEX_UNAVAILABLE';
    throw unavailable;
  }
  return db;
}

/**
 * Create the current schema when absent.  If a prior or damaged workflow-os schema
 * is found, only workflow-os tables are dropped and recreated.  This is safe
 * because the database is a cache of Markdown, not a source of truth.
 *
 * @param {DatabaseSync} db
 * @returns {{schemaVersion: number, rebuilt: boolean}}
 */
export function createSchema(db) {
  assertDatabase(db);
  configureConnection(db);

  if (schemaIsCompatible(db)) {
    // Keep index creation idempotent in case an index was removed manually.
    db.exec(CREATE_SCHEMA_SQL);
    return { schemaVersion: SCHEMA_VERSION, rebuilt: false };
  }

  rebuildSchemaInternal(db);
  return { schemaVersion: SCHEMA_VERSION, rebuilt: true };
}

/**
 * Clear and recreate the derived schema.  Use this for an explicit rebuild;
 * callers must re-index Markdown documents afterwards.
 *
 * @param {DatabaseSync} db
 * @returns {{schemaVersion: number, rebuilt: true}}
 */
export function rebuildSchema(db) {
  assertDatabase(db);
  configureConnection(db);
  rebuildSchemaInternal(db);
  return { schemaVersion: SCHEMA_VERSION, rebuilt: true };
}

function configureConnection(db) {
  // WAL makes independent readers practical; the lock file in the CLI still
  // serializes writers.  `busy_timeout` gives a short, predictable wait before
  // SQLite reports the actionable busy error to that caller.
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec(`PRAGMA busy_timeout = ${BUSY_TIMEOUT_MS};`);
  db.exec('PRAGMA journal_mode = WAL;');
}

function schemaIsCompatible(db) {
  for (const [table, requiredColumns] of Object.entries(REQUIRED_COLUMNS)) {
    if (!tableExists(db, table)) return false;
    const columns = new Set(db.prepare(`PRAGMA table_info(${table})`).all().map((row) => row.name));
    if (!requiredColumns.every((column) => columns.has(column))) return false;
  }

  const version = db.prepare('SELECT value FROM meta WHERE key = ?').get(SCHEMA_VERSION_KEY);
  return version?.value === String(SCHEMA_VERSION);
}

function rebuildSchemaInternal(db) {
  // Foreign keys must be disabled before beginning the transaction to allow
  // deterministic dropping should a previous version have stricter relations.
  db.exec('PRAGMA foreign_keys = OFF;');
  try {
    inTransaction(db, () => {
      db.exec(DROP_SCHEMA_SQL);
      db.exec(CREATE_SCHEMA_SQL);
      db.prepare('INSERT INTO meta (key, value) VALUES (?, ?)').run(
        SCHEMA_VERSION_KEY,
        String(SCHEMA_VERSION),
      );
    });
  } finally {
    db.exec('PRAGMA foreign_keys = ON;');
  }
}
