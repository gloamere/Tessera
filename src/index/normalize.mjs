/**
 * Validate and normalize the payload handed to the writer.
 *
 * Nothing here touches SQLite; these are pure functions over plain objects.
 */

import { nonEmptyText, optionalText, textOrEmpty } from './internal.mjs';

export function normalizeDocument(document) {
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
