/**
 * The only two functions that mutate the derived index.
 */

import { assertDatabase, inTransaction, nonEmptyText } from './internal.mjs';

import { normalizeDocument } from './normalize.mjs';

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
