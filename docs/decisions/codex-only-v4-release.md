---
status: accepted
date: 2026-07-23
decision-makers: Gloamere maintainers
---

# Gloamere 4.0 adopts a Codex-only two-plugin release

## Context

The previous distribution mixed a legacy brand, two host formats, eight public
plugin IDs, mutable-branch installation, and duplicated version declarations.
That surface increased release drift, made public positioning unclear, and
allowed old and new routing descriptions to coexist without an explicit
migration boundary.

## Decision

Gloamere 4.0 is **Codex-only** and publishes exactly two plugins:

- `gloamere-eval`, containing `gloamere-skill-eval`;
- `gloamere-workflows`, containing four independently routed professional
  workflow skills.

The distribution version is `4.0.0-beta.1`. Each plugin starts an independent
package version at `1.0.0-beta.1`.

`release-manifest.json` is the single release source of truth for repository,
distribution version, tag, marketplace policy, plugin paths, plugin versions,
bundled skill sets, archive names, checksums, and legacy behavior. A
deterministic generator derives marketplace JSON and the release download
index. Native consumer files such as `VERSION`, plugin manifests, and installers
mirror the remaining values and are checked in CI.

Installations and documentation pin immutable tag `v4.0.0-beta.1`. A release
builds one deterministic ZIP plus a SHA-256 sidecar for each plugin after the
same complete checks pass on Ubuntu, macOS, and Windows. CI covers Python
3.10–3.14 and both Windows PowerShell 5.1 and PowerShell 7 launcher paths.

Legacy `@tessera` installations are detected read-only. Installers must print
the user-controlled migration sequence and stop before changing state; they
must not remove, disable, migrate, or rewrite the old installation.

## Consequences

- Public identity, repository, selectors, and assets are consistent under the
  Gloamere brand.
- Users can install Eval without the workflow bundle.
- Workflow skills share one product package while retaining independent routing
  descriptions.
- Mutable `main` installs are no longer documented or accepted as release
  evidence.
- Earlier ADRs and evaluation evidence remain unchanged for traceability, but
  they do not define the v4 public release.
- The breaking namespace transition requires the explicit
  [migration guide](../../MIGRATION.md).
