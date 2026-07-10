/**
 * Read-only queries.  Every result is a plain JSON-safe object.
 */

import { assertDatabase, nonEmptyText } from './internal.mjs';

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
