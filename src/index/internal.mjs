/**
 * Shared low-level helpers: argument checks and transaction plumbing.
 */

export const BUSY_TIMEOUT_MS = 1_500;

export function tableExists(db, table) {
  return Boolean(
    db.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?").get(table),
  );
}

export function inTransaction(db, callback) {
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

export function assertDatabase(db) {
  if (!db || typeof db.prepare !== 'function' || typeof db.exec !== 'function') {
    throw new TypeError('db must be a node:sqlite DatabaseSync instance.');
  }
}

export function nonEmptyText(value, label) {
  if (value === null || value === undefined || String(value).trim() === '') {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  return String(value);
}

export function optionalText(value) {
  if (value === null || value === undefined) return null;
  const text = String(value);
  return text.trim() === '' ? null : text;
}

export function textOrEmpty(value) {
  return value === null || value === undefined ? '' : String(value);
}
