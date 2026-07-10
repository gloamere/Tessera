/**
 * The local, derived SQLite index used by workflow-os.
 *
 * Markdown is the source of truth.  This module deliberately only persists
 * metadata which can be recreated by scanning Markdown files, and never
 * stores document bodies.  All exported query results are plain JSON-safe
 * objects so a CLI can render them directly or serialize them with JSON.
 */
import { DatabaseSync } from 'node:sqlite';

/** Current shape of the derived index. */
export const SCHEMA_VERSION = 3;

const BUSY_TIMEOUT_MS = 1_500;
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

/**
 * Replace every derived record owned by one Markdown document.
 *
 * Accepted payload shape (all text values are stored as strings):
 *
 * ```js
 * {
 *   path: 'docs/work/mall-ui.md', kind: 'work', title: '商城 UI 改造',
 *   hash: '<sha256>', indexedAt: '<ISO timestamp>', parseError: null,
 *   workItem: {
 *     id: 'work-mall-ui', type: 'ui', status: 'in_progress',
 *     priority: 'high', updatedAt: '<ISO timestamp>', nextStep: '...',
 *     approvalStatus: 'pending', dependencies: ['work-assets']
 *   },
 *   links: [{ sourceKind: 'work_item', sourceId: 'work-mall-ui',
 *     relation: 'depends_on', targetKind: 'work_item', targetId: 'work-assets' }]
 * }
 * ```
 *
 * `decision` accepts `{ id, workItemId, status, updatedAt }`.  `researchItem`
 * accepts `{ id, mode, status, question, scope, recency, updatedAt,
 * nextAction, confirmation, workItemId }`; its associations are represented
 * by canonical `research` / `research_for` links. Both the camelCase link
 * fields above and `fromKind`/`fromId`/`toKind`/`toId` aliases are accepted.
 * A non-empty `parseError` deliberately clears the document's structured
 * metadata and owned links while retaining the document error.
 *
 * @param {DatabaseSync} db
 * @param {object} document
 * @returns {{path: string, kind: string, indexedAt: string, parseError: string|null, workItemId: string|null, decisionId: string|null, researchItemId: string|null, linkCount: number}}
 */
export function replaceDocumentIndex(db, document) {
  assertDatabase(db);
  const normalized = normalizeDocument(document);

  return inTransaction(db, () => {
    // Remove child records first.  This makes a parse error unable to leave
    // old state visible, and also makes a changed frontmatter ID replace cleanly.
    db.prepare('DELETE FROM links WHERE document_path = ?').run(normalized.path);
    db.prepare('DELETE FROM work_items WHERE document_path = ?').run(normalized.path);
    db.prepare('DELETE FROM decisions WHERE document_path = ?').run(normalized.path);
    db.prepare('DELETE FROM research_items WHERE document_path = ?').run(normalized.path);

    db.prepare(`
      INSERT INTO documents (path, kind, title, hash, indexed_at, parse_error)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(path) DO UPDATE SET
        kind = excluded.kind,
        title = excluded.title,
        hash = excluded.hash,
        indexed_at = excluded.indexed_at,
        parse_error = excluded.parse_error
    `).run(
      normalized.path,
      normalized.kind,
      normalized.title,
      normalized.hash,
      normalized.indexedAt,
      normalized.parseError,
    );

    if (normalized.parseError === null) {
      if (normalized.workItem) {
        const item = normalized.workItem;
        db.prepare(`
          INSERT INTO work_items
            (id, document_path, type, status, priority, updated_at, next_step, approval_status, clarification_summary)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          item.id,
          normalized.path,
          item.type,
          item.status,
          item.priority,
          item.updatedAt,
          item.nextStep,
          item.approvalStatus,
          item.clarificationSummary,
        );
      }

      if (normalized.decision) {
        const decision = normalized.decision;
        db.prepare(`
          INSERT INTO decisions (id, document_path, work_item_id, status, updated_at)
          VALUES (?, ?, ?, ?, ?)
        `).run(
          decision.id,
          normalized.path,
          decision.workItemId,
          decision.status,
          decision.updatedAt,
        );
      }

      if (normalized.researchItem) {
        const research = normalized.researchItem;
        db.prepare(`
          INSERT INTO research_items
            (id, document_path, work_item_id, mode, status, question, scope, recency, updated_at, next_action, confirmation)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          research.id,
          normalized.path,
          research.workItemId,
          research.mode,
          research.status,
          research.question,
          research.scope,
          research.recency,
          research.updatedAt,
          research.nextAction,
          research.confirmation,
        );
      }

      const insertLink = db.prepare(`
        INSERT OR IGNORE INTO links
          (document_path, source_kind, source_id, relation, target_kind, target_id)
        VALUES (?, ?, ?, ?, ?, ?)
      `);
      for (const link of normalized.links) {
        insertLink.run(
          normalized.path,
          link.sourceKind,
          link.sourceId,
          link.relation,
          link.targetKind,
          link.targetId,
        );
      }
    }

    return {
      path: normalized.path,
      kind: normalized.kind,
      indexedAt: normalized.indexedAt,
      parseError: normalized.parseError,
      workItemId: normalized.parseError === null && normalized.workItem ? normalized.workItem.id : null,
      decisionId: normalized.parseError === null && normalized.decision ? normalized.decision.id : null,
      researchItemId: normalized.parseError === null && normalized.researchItem ? normalized.researchItem.id : null,
      linkCount: normalized.parseError === null ? normalized.links.length : 0,
    };
  });
}

/**
 * Remove index records for Markdown files absent from the current scan.
 * Paths are compared exactly; the scanner should provide normalized project
 * relative paths consistently on every run.
 *
 * @param {DatabaseSync} db
 * @param {Iterable<string>} presentPaths
 * @returns {{removedCount: number, removedPaths: string[]}}
 */
export function removeMissingDocuments(db, presentPaths) {
  assertDatabase(db);
  if (presentPaths === null || presentPaths === undefined || typeof presentPaths[Symbol.iterator] !== 'function') {
    throw new TypeError('presentPaths must be an iterable of document paths.');
  }

  const present = new Set();
  for (const path of presentPaths) {
    present.add(nonEmptyText(path, 'present document path'));
  }

  return inTransaction(db, () => {
    const indexedPaths = db.prepare('SELECT path FROM documents').all().map((row) => row.path);
    const removedPaths = indexedPaths.filter((path) => !present.has(path));
    const remove = db.prepare('DELETE FROM documents WHERE path = ?');
    for (const path of removedPaths) remove.run(path);
    return { removedCount: removedPaths.length, removedPaths };
  });
}

/**
 * Return the status data needed for a compact project dashboard.
 *
 * Status labels remain user-defined.  The convenience buckets recognize the
 * common English and Chinese labels documented in `matchesStatus` below, while
 * the complete `workItems` and `decisions` arrays preserve every item.
 *
 * @param {DatabaseSync} db
 * @returns {object}
 */
export function queryStatus(db) {
  assertDatabase(db);
  const workItems = db.prepare(`
    SELECT wi.id, wi.document_path, wi.type, wi.status, wi.priority,
           wi.updated_at, wi.next_step, wi.approval_status, wi.clarification_summary,
           d.kind AS document_kind, d.title
      FROM work_items AS wi
      JOIN documents AS d ON d.path = wi.document_path
     ORDER BY COALESCE(wi.updated_at, d.indexed_at) DESC, wi.id ASC, wi.document_path ASC
  `).all().map(mapWorkItem);

  const decisions = db.prepare(`
    SELECT de.id, de.document_path, de.work_item_id, de.status, de.updated_at,
           d.kind AS document_kind, d.title
      FROM decisions AS de
      JOIN documents AS d ON d.path = de.document_path
     ORDER BY COALESCE(de.updated_at, d.indexed_at) DESC, de.id ASC, de.document_path ASC
  `).all().map(mapDecision);

  const researchItems = db.prepare(`
    SELECT ri.id, ri.document_path, ri.work_item_id, ri.mode, ri.status,
           ri.question, ri.scope, ri.recency, ri.updated_at, ri.next_action, ri.confirmation,
           d.kind AS document_kind, d.title
      FROM research_items AS ri
      JOIN documents AS d ON d.path = ri.document_path
     ORDER BY COALESCE(ri.updated_at, d.indexed_at) DESC, ri.id ASC, ri.document_path ASC
  `).all().map(mapResearchItem);

  const parseErrors = db.prepare(`
    SELECT path, kind, title, indexed_at, parse_error
      FROM documents
     WHERE parse_error IS NOT NULL AND TRIM(parse_error) <> ''
     ORDER BY path ASC
  `).all().map((row) => ({
    path: row.path,
    kind: row.kind,
    title: row.title,
    indexedAt: row.indexed_at,
    parseError: row.parse_error,
  }));

  const inProgress = workItems.filter((item) => matchesStatus(item.status, 'inProgress'));
  const blocked = workItems.filter((item) => matchesStatus(item.status, 'blocked'));
  const needsClarification = workItems.filter((item) => matchesStatus(item.status, 'clarification'));
  const activeResearch = researchItems.filter((item) => (
    !matchesStatus(item.status, 'complete') && !matchesStatus(item.status, 'cancelled')
  ));
  const blockedResearch = researchItems.filter((item) => matchesStatus(item.status, 'blocked'));
  const pendingResearchConfirmation = researchItems.filter((item) => matchesStatus(item.confirmation, 'pending'));
  const pendingApproval = [
    ...workItems
      .filter((item) => matchesStatus(item.approvalStatus, 'pending') || matchesStatus(item.status, 'pending'))
      .map((item) => ({ entityKind: 'work_item', ...item })),
    ...decisions
      .filter((decision) => matchesStatus(decision.status, 'pending'))
      .map((decision) => ({ entityKind: 'decision', ...decision })),
  ];

  const nextSteps = workItems
    .filter((item) => item.nextStep !== null && item.nextStep.trim() !== '')
    .filter((item) => !matchesStatus(item.status, 'complete') && !matchesStatus(item.status, 'cancelled'))
    .map((item) => ({
      id: item.id,
      path: item.path,
      title: item.title,
      status: item.status,
      nextStep: item.nextStep,
    }));

  return {
    generatedAt: new Date().toISOString(),
    totals: {
      workItems: workItems.length,
      decisions: decisions.length,
      researchItems: researchItems.length,
      parseErrors: parseErrors.length,
    },
    workItems,
    decisions,
    researchItems,
    inProgress,
    blocked,
    needsClarification,
    activeResearch,
    blockedResearch,
    pendingResearchConfirmation,
    pendingApproval,
    nextSteps,
    parseErrors,
  };
}

/**
 * Return the content hashes currently represented by the derived index.
 * The CLI uses these values for incremental Markdown scanning; callers never
 * need to trust timestamps from a filesystem or a network checkout.
 *
 * @param {DatabaseSync} db
 * @returns {{path: string, hash: string}[]}
 */
export function queryDocumentHashes(db) {
  assertDatabase(db);
  return db.prepare('SELECT path, hash FROM documents ORDER BY path ASC').all().map((row) => ({
    path: row.path,
    hash: row.hash,
  }));
}

/**
 * Return the small structured context package for exactly one work-item ID.
 * Document bodies intentionally are not included; the caller can read the
 * returned Markdown paths only when it needs the detailed brief.
 *
 * @param {DatabaseSync} db
 * @param {string} workItemId
 * @returns {object}
 */
export function queryContext(db, workItemId) {
  assertDatabase(db);
  const id = nonEmptyText(workItemId, 'work item ID');
  const candidates = findWorkItemsById(db, id);

  if (candidates.length === 0) {
    return {
      workItemId: id,
      workItem: null,
      error: {
        code: 'work_item_not_found',
        message: `No work item with ID "${id}" is indexed.`,
      },
      dependencies: [],
      decisions: [],
      researchItems: [],
      links: [],
    };
  }

  if (candidates.length > 1) {
    return {
      workItemId: id,
      workItem: null,
      error: {
        code: 'ambiguous_work_item_id',
        message: `Work item ID "${id}" is used by ${candidates.length} documents.`,
      },
      candidates,
      dependencies: [],
      decisions: [],
      researchItems: [],
      links: [],
    };
  }

  const workItem = candidates[0];
  const links = db.prepare(`
    SELECT document_path, source_kind, source_id, relation, target_kind, target_id
      FROM links
     WHERE (source_kind = 'work_item' AND source_id = ?)
        OR (target_kind = 'work_item' AND target_id = ?)
     ORDER BY document_path ASC, source_kind ASC, source_id ASC, relation ASC, target_kind ASC, target_id ASC
  `).all(id, id).map(mapLink);

  const dependencyLinks = links.filter((link) => (
    link.sourceKind === 'work_item'
    && link.sourceId === id
    && isDependencyRelation(link.relation)
    && link.targetKind === 'work_item'
  ));
  const dependencies = dependencyLinks.map((link) => ({
    link,
    ...resolveWorkItemReference(db, link.targetId),
  }));

  const decisionIds = new Set(
    db.prepare('SELECT id FROM decisions WHERE work_item_id = ?').all(id).map((row) => row.id),
  );
  for (const link of links) {
    if (link.sourceKind === 'work_item' && link.sourceId === id && link.targetKind === 'decision') {
      decisionIds.add(link.targetId);
    }
    if (link.targetKind === 'work_item' && link.targetId === id && link.sourceKind === 'decision') {
      decisionIds.add(link.sourceId);
    }
  }

  const decisionRows = [];
  const seenDecisionRows = new Set();
  for (const decisionId of [...decisionIds].sort()) {
    for (const decision of findDecisionsById(db, decisionId)) {
      const key = `${decision.id}\u0000${decision.path}`;
      if (!seenDecisionRows.has(key)) {
        seenDecisionRows.add(key);
        decisionRows.push(decision);
      }
    }
  }

  const researchIds = new Set(
    db.prepare('SELECT id FROM research_items WHERE work_item_id = ?').all(id).map((row) => row.id),
  );
  for (const link of links) {
    if (link.sourceKind === 'work_item' && link.sourceId === id && link.targetKind === 'research') {
      researchIds.add(link.targetId);
    }
    if (link.targetKind === 'work_item' && link.targetId === id && link.sourceKind === 'research') {
      researchIds.add(link.sourceId);
    }
  }
  const researchRows = collectResearchItemsByIds(db, researchIds);

  return {
    workItemId: id,
    workItem,
    error: null,
    dependencies,
    decisions: decisionRows,
    researchItems: researchRows,
    links,
  };
}

/**
 * Return the compact context package for exactly one research-item ID.
 * As with `queryContext`, source notes remain in Markdown; this result only
 * identifies the relevant document, linked work item, decisions, and research
 * dependencies a specialized agent should load.
 *
 * @param {DatabaseSync} db
 * @param {string} researchItemId
 * @returns {object}
 */
export function queryResearchContext(db, researchItemId) {
  assertDatabase(db);
  const id = nonEmptyText(researchItemId, 'research item ID');
  const candidates = findResearchItemsById(db, id);

  if (candidates.length === 0) {
    return {
      researchItemId: id,
      researchItem: null,
      error: {
        code: 'research_item_not_found',
        message: `No research item with ID "${id}" is indexed.`,
      },
      workItem: null,
      dependencies: [],
      decisions: [],
      links: [],
    };
  }

  if (candidates.length > 1) {
    return {
      researchItemId: id,
      researchItem: null,
      error: {
        code: 'ambiguous_research_item_id',
        message: `Research item ID "${id}" is used by ${candidates.length} documents.`,
      },
      candidates,
      workItem: null,
      dependencies: [],
      decisions: [],
      links: [],
    };
  }

  const researchItem = candidates[0];
  const links = db.prepare(`
    SELECT document_path, source_kind, source_id, relation, target_kind, target_id
      FROM links
     WHERE (source_kind = 'research' AND source_id = ?)
        OR (target_kind = 'research' AND target_id = ?)
     ORDER BY document_path ASC, source_kind ASC, source_id ASC, relation ASC, target_kind ASC, target_id ASC
  `).all(id, id).map(mapLink);

  const workItemIds = new Set();
  if (researchItem.workItemId) workItemIds.add(researchItem.workItemId);
  for (const link of links) {
    if (link.sourceKind === 'research' && link.sourceId === id && link.targetKind === 'work_item') {
      workItemIds.add(link.targetId);
    }
    if (link.targetKind === 'research' && link.targetId === id && link.sourceKind === 'work_item') {
      workItemIds.add(link.sourceId);
    }
  }
  const workItems = [...workItemIds].sort().map((workItemId) => ({
    workItemId,
    ...resolveWorkItemReference(db, workItemId),
  }));

  const dependencyLinks = links.filter((link) => (
    link.sourceKind === 'research'
    && link.sourceId === id
    && isDependencyRelation(link.relation)
    && link.targetKind === 'research'
  ));
  const dependencies = dependencyLinks.map((link) => ({
    link,
    ...resolveResearchItemReference(db, link.targetId),
  }));

  const decisionIds = new Set();
  for (const link of links) {
    if (link.sourceKind === 'research' && link.sourceId === id && link.targetKind === 'decision') {
      decisionIds.add(link.targetId);
    }
    if (link.targetKind === 'research' && link.targetId === id && link.sourceKind === 'decision') {
      decisionIds.add(link.sourceId);
    }
  }

  return {
    researchItemId: id,
    researchItem,
    error: null,
    workItem: workItems.length === 1 ? workItems[0].workItem : null,
    workItems,
    dependencies,
    decisions: collectDecisionsByIds(db, decisionIds),
    links,
  };
}

/**
 * Inspect index consistency without mutating it.
 *
 * Duplicate IDs are intentionally detectable, as are dangling/ambiguous
 * polymorphic links and a decision that points at a missing work item.
 * Frontmatter syntax errors should be supplied to `replaceDocumentIndex` as
 * `parseError` by the Markdown parser and are returned here as parse errors.
 *
 * @param {DatabaseSync} db
 * @returns {object}
 */
export function queryValidation(db) {
  assertDatabase(db);

  const parseErrors = db.prepare(`
    SELECT path, kind, title, indexed_at, parse_error
      FROM documents
     WHERE parse_error IS NOT NULL AND TRIM(parse_error) <> ''
     ORDER BY path ASC
  `).all().map((row) => ({
    path: row.path,
    kind: row.kind,
    title: row.title,
    indexedAt: row.indexed_at,
    message: row.parse_error,
  }));

  const duplicateWorkItemIds = findDuplicateIds(db, 'work_items', 'work item');
  const duplicateDecisionIds = findDuplicateIds(db, 'decisions', 'decision');
  const duplicateResearchItemIds = findDuplicateIds(db, 'research_items', 'research item');

  const workCounts = countById(db, 'work_items');
  const decisionCounts = countById(db, 'decisions');
  const researchCounts = countById(db, 'research_items');
  const entityCounts = new Map([
    ['work_item', workCounts],
    ['decision', decisionCounts],
    ['research', researchCounts],
  ]);

  const brokenLinks = [];
  for (const link of db.prepare(`
    SELECT document_path, source_kind, source_id, relation, target_kind, target_id
      FROM links
     ORDER BY document_path ASC, row_id ASC
  `).all().map(mapLink)) {
    const sourceState = referenceState(entityCounts, link.sourceKind, link.sourceId);
    const targetState = referenceState(entityCounts, link.targetKind, link.targetId);
    if (sourceState !== 'resolved') {
      brokenLinks.push({ ...link, end: 'source', reason: sourceState });
    }
    if (targetState !== 'resolved') {
      brokenLinks.push({ ...link, end: 'target', reason: targetState });
    }
  }

  const invalidDecisionWorkItems = [];
  for (const decision of db.prepare(`
    SELECT de.id, de.document_path, de.work_item_id
      FROM decisions AS de
     WHERE de.work_item_id IS NOT NULL AND TRIM(de.work_item_id) <> ''
     ORDER BY de.document_path ASC
  `).all()) {
    const state = referenceState(entityCounts, 'work_item', decision.work_item_id);
    if (state !== 'resolved') {
      invalidDecisionWorkItems.push({
        decisionId: decision.id,
        path: decision.document_path,
        workItemId: decision.work_item_id,
        reason: state,
      });
    }
  }

  const invalidResearchWorkItems = [];
  for (const research of db.prepare(`
    SELECT ri.id, ri.document_path, ri.work_item_id
      FROM research_items AS ri
     WHERE ri.work_item_id IS NOT NULL AND TRIM(ri.work_item_id) <> ''
     ORDER BY ri.document_path ASC
  `).all()) {
    const state = referenceState(entityCounts, 'work_item', research.work_item_id);
    if (state !== 'resolved') {
      invalidResearchWorkItems.push({
        researchItemId: research.id,
        path: research.document_path,
        workItemId: research.work_item_id,
        reason: state,
      });
    }
  }

  const errors = [
    ...parseErrors.map((error) => ({ code: 'parse_error', ...error })),
    ...duplicateWorkItemIds.map((error) => ({ code: 'duplicate_work_item_id', ...error })),
    ...duplicateDecisionIds.map((error) => ({ code: 'duplicate_decision_id', ...error })),
    ...duplicateResearchItemIds.map((error) => ({ code: 'duplicate_research_item_id', ...error })),
    ...brokenLinks.map((error) => ({ code: 'broken_link', ...error })),
    ...invalidDecisionWorkItems.map((error) => ({ code: 'invalid_decision_work_item', ...error })),
    ...invalidResearchWorkItems.map((error) => ({ code: 'invalid_research_work_item', ...error })),
  ];

  return {
    valid: errors.length === 0,
    parseErrors,
    duplicateWorkItemIds,
    duplicateDecisionIds,
    duplicateResearchItemIds,
    brokenLinks,
    invalidDecisionWorkItems,
    invalidResearchWorkItems,
    errors,
  };
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

function tableExists(db, table) {
  return Boolean(
    db.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?").get(table),
  );
}

function inTransaction(db, callback) {
  db.exec('BEGIN IMMEDIATE;');
  try {
    const result = callback();
    db.exec('COMMIT;');
    return result;
  } catch (error) {
    try {
      db.exec('ROLLBACK;');
    } catch {
      // Preserve the original error.  A failed rollback only occurs if SQLite
      // already aborted the transaction.
    }
    throw error;
  }
}

function normalizeDocument(document) {
  if (!document || typeof document !== 'object' || Array.isArray(document)) {
    throw new TypeError('document must be an object.');
  }

  const path = nonEmptyText(document.path, 'document.path');
  const kind = nonEmptyText(document.kind, 'document.kind');
  const title = textOrEmpty(document.title);
  const hash = textOrEmpty(document.hash);
  const indexedAt = optionalText(document.indexedAt) ?? new Date().toISOString();
  const parseError = optionalText(document.parseError);

  if (parseError !== null) {
    return {
      path,
      kind,
      title,
      hash,
      indexedAt,
      parseError,
      workItem: null,
      decision: null,
      researchItem: null,
      links: [],
    };
  }

  const records = [document.workItem, document.decision, document.researchItem].filter(Boolean);
  if (records.length > 1) {
    throw new TypeError('A document may contain one of workItem, decision, or researchItem metadata.');
  }

  const workItem = document.workItem ? normalizeWorkItem(document.workItem, indexedAt) : null;
  const decision = document.decision ? normalizeDecision(document.decision, indexedAt) : null;
  const researchItem = document.researchItem ? normalizeResearchItem(document.researchItem, indexedAt) : null;
  const links = normalizeLinks(document.links, workItem, decision, researchItem);

  if (workItem) {
    for (const dependency of normalizeReferenceList(workItem.dependencies, 'workItem.dependencies')) {
      links.push({
        sourceKind: 'work_item',
        sourceId: workItem.id,
        relation: 'depends_on',
        targetKind: 'work_item',
        targetId: dependency.id,
      });
    }
    for (const decisionReference of normalizeReferenceList(workItem.decisionIds, 'workItem.decisionIds')) {
      links.push({
        sourceKind: 'work_item',
        sourceId: workItem.id,
        relation: 'has_decision',
        targetKind: 'decision',
        targetId: decisionReference.id,
      });
    }
  }

  if (decision?.workItemId) {
    links.push({
      sourceKind: 'decision',
      sourceId: decision.id,
      relation: 'for_work_item',
      targetKind: 'work_item',
      targetId: decision.workItemId,
    });
  }

  if (researchItem?.workItemId) {
    links.push({
      sourceKind: 'research',
      sourceId: researchItem.id,
      relation: 'research_for',
      targetKind: 'work_item',
      targetId: researchItem.workItemId,
    });
  }

  return {
    path,
    kind,
    title,
    hash,
    indexedAt,
    parseError: null,
    workItem,
    decision,
    researchItem,
    links: deduplicateLinks(links),
  };
}

function normalizeWorkItem(item, fallbackUpdatedAt) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    throw new TypeError('document.workItem must be an object.');
  }
  return {
    id: nonEmptyText(item.id, 'workItem.id'),
    type: optionalText(item.type),
    status: optionalText(item.status),
    priority: optionalText(item.priority),
    updatedAt: optionalText(item.updatedAt ?? item.updated) ?? fallbackUpdatedAt,
    nextStep: optionalText(item.nextStep ?? item.next),
    approvalStatus: optionalText(item.approvalStatus ?? item.approval),
    clarificationSummary: optionalText(item.clarificationSummary ?? item.clarification),
    dependencies: item.dependencies ?? item.dependsOn ?? [],
    decisionIds: item.decisionIds ?? item.decisions ?? [],
  };
}

function normalizeDecision(decision, fallbackUpdatedAt) {
  if (!decision || typeof decision !== 'object' || Array.isArray(decision)) {
    throw new TypeError('document.decision must be an object.');
  }
  return {
    id: nonEmptyText(decision.id, 'decision.id'),
    workItemId: optionalText(decision.workItemId ?? decision.workItem),
    status: optionalText(decision.status),
    updatedAt: optionalText(decision.updatedAt ?? decision.updated) ?? fallbackUpdatedAt,
  };
}

function normalizeResearchItem(research, fallbackUpdatedAt) {
  if (!research || typeof research !== 'object' || Array.isArray(research)) {
    throw new TypeError('document.researchItem must be an object.');
  }
  return {
    id: nonEmptyText(research.id, 'researchItem.id'),
    mode: optionalText(research.mode),
    status: optionalText(research.status),
    question: optionalText(research.question),
    scope: optionalText(research.scope),
    recency: optionalText(research.recency),
    updatedAt: optionalText(research.updatedAt ?? research.updated) ?? fallbackUpdatedAt,
    nextAction: optionalText(research.nextAction ?? research.next_action),
    confirmation: optionalText(research.confirmation),
    workItemId: optionalText(research.workItemId ?? research.work_item),
  };
}

function normalizeLinks(rawLinks, workItem, decision, researchItem) {
  if (rawLinks === null || rawLinks === undefined) return [];
  if (!Array.isArray(rawLinks)) throw new TypeError('document.links must be an array.');

  return rawLinks.map((rawLink, index) => {
    if (!rawLink || typeof rawLink !== 'object' || Array.isArray(rawLink)) {
      throw new TypeError(`document.links[${index}] must be an object.`);
    }
    const inferredSource = workItem
      ? { kind: 'work_item', id: workItem.id }
      : decision
        ? { kind: 'decision', id: decision.id }
        : researchItem
          ? { kind: 'research', id: researchItem.id }
          : null;
    const sourceKind = normalizeEntityKind(rawLink.sourceKind ?? rawLink.fromKind ?? inferredSource?.kind, `links[${index}].sourceKind`);
    const sourceId = nonEmptyText(rawLink.sourceId ?? rawLink.fromId ?? inferredSource?.id, `links[${index}].sourceId`);
    const relation = nonEmptyText(rawLink.relation, `links[${index}].relation`);
    const targetKind = normalizeEntityKind(rawLink.targetKind ?? rawLink.toKind, `links[${index}].targetKind`);
    const targetId = nonEmptyText(rawLink.targetId ?? rawLink.toId, `links[${index}].targetId`);
    return { sourceKind, sourceId, relation, targetKind, targetId };
  });
}

function normalizeReferenceList(value, label) {
  if (value === null || value === undefined) return [];
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value.map((entry, index) => {
    if (typeof entry === 'string' || typeof entry === 'number') {
      return { id: nonEmptyText(entry, `${label}[${index}]`) };
    }
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new TypeError(`${label}[${index}] must be an ID or object with an id.`);
    }
    return { id: nonEmptyText(entry.id ?? entry.targetId, `${label}[${index}].id`) };
  });
}

function deduplicateLinks(links) {
  const seen = new Set();
  return links.filter((link) => {
    const key = [link.sourceKind, link.sourceId, link.relation, link.targetKind, link.targetId].join('\u0000');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizeEntityKind(value, label) {
  const normalized = nonEmptyText(value, label).trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'work' || normalized === 'workitem' || normalized === 'work_item') return 'work_item';
  if (normalized === 'decision' || normalized === 'decisions') return 'decision';
  if (normalized === 'research' || normalized === 'researchitem' || normalized === 'research_item') return 'research';
  return normalized;
}

function mapWorkItem(row) {
  return {
    id: row.id,
    path: row.document_path,
    title: row.title,
    documentKind: row.document_kind,
    type: row.type,
    status: row.status,
    priority: row.priority,
    updatedAt: row.updated_at,
    nextStep: row.next_step,
    approvalStatus: row.approval_status,
    clarificationSummary: row.clarification_summary,
  };
}

function mapDecision(row) {
  return {
    id: row.id,
    path: row.document_path,
    title: row.title,
    documentKind: row.document_kind,
    workItemId: row.work_item_id,
    status: row.status,
    updatedAt: row.updated_at,
  };
}

function mapResearchItem(row) {
  return {
    id: row.id,
    path: row.document_path,
    title: row.title,
    documentKind: row.document_kind,
    workItemId: row.work_item_id,
    mode: row.mode,
    status: row.status,
    question: row.question,
    scope: row.scope,
    recency: row.recency,
    updatedAt: row.updated_at,
    nextAction: row.next_action,
    confirmation: row.confirmation,
  };
}

function mapLink(row) {
  return {
    path: row.document_path,
    sourceKind: row.source_kind,
    sourceId: row.source_id,
    relation: row.relation,
    targetKind: row.target_kind,
    targetId: row.target_id,
  };
}

function findWorkItemsById(db, id) {
  return db.prepare(`
    SELECT wi.id, wi.document_path, wi.type, wi.status, wi.priority,
           wi.updated_at, wi.next_step, wi.approval_status, wi.clarification_summary,
           d.kind AS document_kind, d.title
      FROM work_items AS wi
      JOIN documents AS d ON d.path = wi.document_path
     WHERE wi.id = ?
     ORDER BY wi.document_path ASC
  `).all(id).map(mapWorkItem);
}

function findDecisionsById(db, id) {
  return db.prepare(`
    SELECT de.id, de.document_path, de.work_item_id, de.status, de.updated_at,
           d.kind AS document_kind, d.title
      FROM decisions AS de
      JOIN documents AS d ON d.path = de.document_path
     WHERE de.id = ?
     ORDER BY de.document_path ASC
  `).all(id).map(mapDecision);
}

function findResearchItemsById(db, id) {
  return db.prepare(`
    SELECT ri.id, ri.document_path, ri.work_item_id, ri.mode, ri.status,
           ri.question, ri.scope, ri.recency, ri.updated_at, ri.next_action, ri.confirmation,
           d.kind AS document_kind, d.title
      FROM research_items AS ri
      JOIN documents AS d ON d.path = ri.document_path
     WHERE ri.id = ?
     ORDER BY ri.document_path ASC
  `).all(id).map(mapResearchItem);
}

function collectDecisionsByIds(db, ids) {
  const decisions = [];
  const seen = new Set();
  for (const id of [...ids].sort()) {
    for (const decision of findDecisionsById(db, id)) {
      const key = `${decision.id}\u0000${decision.path}`;
      if (!seen.has(key)) {
        seen.add(key);
        decisions.push(decision);
      }
    }
  }
  return decisions;
}

function collectResearchItemsByIds(db, ids) {
  const researchItems = [];
  const seen = new Set();
  for (const id of [...ids].sort()) {
    for (const researchItem of findResearchItemsById(db, id)) {
      const key = `${researchItem.id}\u0000${researchItem.path}`;
      if (!seen.has(key)) {
        seen.add(key);
        researchItems.push(researchItem);
      }
    }
  }
  return researchItems;
}

function resolveWorkItemReference(db, id) {
  const candidates = findWorkItemsById(db, id);
  if (candidates.length === 1) return { state: 'resolved', workItem: candidates[0] };
  if (candidates.length === 0) return { state: 'missing', workItem: null };
  return { state: 'ambiguous', workItem: null, candidates };
}

function resolveResearchItemReference(db, id) {
  const candidates = findResearchItemsById(db, id);
  if (candidates.length === 1) return { state: 'resolved', researchItem: candidates[0] };
  if (candidates.length === 0) return { state: 'missing', researchItem: null };
  return { state: 'ambiguous', researchItem: null, candidates };
}

function findDuplicateIds(db, table, label) {
  // `table` is only called with module-owned constants, never caller input.
  const duplicateIds = db.prepare(`
    SELECT id, COUNT(*) AS count
      FROM ${table}
     GROUP BY id
    HAVING COUNT(*) > 1
     ORDER BY id ASC
  `).all();
  const pathsForId = db.prepare(`SELECT document_path FROM ${table} WHERE id = ? ORDER BY document_path ASC`);
  return duplicateIds.map((row) => ({
    id: row.id,
    count: Number(row.count),
    entity: label,
    paths: pathsForId.all(row.id).map((path) => path.document_path),
  }));
}

function countById(db, table) {
  const counts = new Map();
  // `table` is only called with module-owned constants, never caller input.
  for (const row of db.prepare(`SELECT id, COUNT(*) AS count FROM ${table} GROUP BY id`).all()) {
    counts.set(row.id, Number(row.count));
  }
  return counts;
}

function referenceState(entityCounts, kind, id) {
  const counts = entityCounts.get(kind);
  // Links to extensible, non-indexed entity kinds are not invalid in v1.
  if (!counts) return 'unverified';
  const count = counts.get(id) ?? 0;
  if (count === 1) return 'resolved';
  return count === 0 ? 'missing' : 'ambiguous';
}

function matchesStatus(value, bucket) {
  if (value === null || value === undefined) return false;
  const normalized = String(value).trim().toLowerCase().replace(/[\s-]+/g, '_');
  const labels = {
    inProgress: new Set(['in_progress', 'inprogress', 'active', 'doing', '进行中']),
    blocked: new Set(['blocked', 'blocking', 'stuck', '阻塞', '已阻塞']),
    clarification: new Set(['waiting_clarification', 'needs_clarification', '待澄清']),
    pending: new Set([
      'pending',
      'pending_approval',
      'needs_approval',
      'awaiting_approval',
      'awaiting_decision',
      '待拍板',
      '待确认',
      '待审批',
    ]),
    complete: new Set(['complete', 'completed', 'done', 'closed', '完成', '已完成']),
    cancelled: new Set(['cancelled', 'canceled', 'abandoned', '取消', '已取消']),
  };
  return labels[bucket]?.has(normalized) ?? false;
}

function isDependencyRelation(relation) {
  const normalized = String(relation).trim().toLowerCase().replace(/[\s-]+/g, '_');
  return normalized === 'depends_on' || normalized === 'dependency' || normalized === 'depends';
}

function assertDatabase(db) {
  if (!db || typeof db.prepare !== 'function' || typeof db.exec !== 'function') {
    throw new TypeError('db must be a node:sqlite DatabaseSync instance.');
  }
}

function nonEmptyText(value, label) {
  if (value === null || value === undefined || String(value).trim() === '') {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  return String(value);
}

function optionalText(value) {
  if (value === null || value === undefined) return null;
  const text = String(value);
  return text.trim() === '' ? null : text;
}

function textOrEmpty(value) {
  return value === null || value === undefined ? '' : String(value);
}
