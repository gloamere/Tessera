/**
 * The local, derived SQLite index used by workflow-os.
 *
 * Markdown is the source of truth.  This module deliberately only persists
 * metadata which can be recreated by scanning Markdown files, and never
 * stores document bodies.  All exported query results are plain JSON-safe
 * objects so a CLI can render them directly or serialize them with JSON.
 *
 * The implementation is split by responsibility; this file is the public
 * surface and the only entry point callers should import:
 *
 * - `index/schema.mjs`    opening, migrating and rebuilding the schema
 * - `index/normalize.mjs` pure validation of a document payload
 * - `index/write.mjs`     the only functions that mutate the index
 * - `index/queries.mjs`   read-only queries
 * - `index/internal.mjs`  shared argument checks and transaction plumbing
 */
export {
  SCHEMA_VERSION,
  createSchema,
  openIndex,
  openIndexForRead,
  rebuildSchema,
} from './index/schema.mjs';

export {
  removeMissingDocuments,
  replaceDocumentIndex,
} from './index/write.mjs';

export {
  queryContext,
  queryDocumentHashes,
  queryResearchContext,
  queryStatus,
  queryValidation,
} from './index/queries.mjs';
