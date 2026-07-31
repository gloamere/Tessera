---
status: accepted
date: 2026-07-31
decision-makers: Gloamere maintainers
---

# Gloamere 4 will ship through its Git marketplace without MCP

## Context

The three-workflow product and risk-tiered evaluation design remain valid, but
an official-directory submission is not required for the current owner-run
distribution. Making directory review, publisher-region selection, a hosted
demo, or a participant-count gate block `v4.0.0` adds external work without
improving the installed Skills.

The repository and `codex.gloamere.com` are already controlled distribution and
support surfaces. The intended repository-marketplace targets are the ChatGPT
desktop plugin surface and Codex CLI. ChatGPT desktop has not yet passed a
package smoke test, and there is no evidence for claiming a self-hosted
Git-marketplace installation path on ChatGPT Work web.

Product Decision, Visual Review, and Knowledge Capture use user-provided
evidence and existing host capabilities. None currently requires live service
data, plugin-owned authentication, or controlled remote writes.

## Decision

Distribution `4.0.0` will ship from the `gloamere/codex-plugins` Git marketplace
at immutable tag `v4.0.0`. Until that tag exists, only explicit local-checkout
testing is valid. `gloamere-workflows@1.0.0` remains the default profile;
`gloamere-eval@1.0.0-beta.1` remains maintainer-only.
`release-manifest.json` remains the source of truth for the
distribution channel, package identities, install profiles, and release gate.
The website provides documentation, support, and release
links, but is not a runtime backend and does not receive workflow inputs.

Official-directory material is retained as an optional future channel. Its
102-case exhaustive run, dogfood record, country availability, demo recording,
portal validation, and approval do not block the Git tag or GitHub release.
Directory availability must never be claimed before a verified listing exists.

`v4.0.0` remains skills-only and does not enable MCP. A future MCP candidate
must be separately scoped after a live-data or controlled-action need recurs
and cannot be solved with host-native capabilities. It must begin as a
read-only `search`/`fetch` experiment and demonstrate a net benefit before any
authentication or write scope is considered, including permission, privacy,
failure-mode, maintenance, and token-cost review.

## Consequences

- Ordinary users get a direct, pinned Git-marketplace installation path.
- Intended self-hosted targets are ChatGPT desktop and Codex CLI; the desktop
  target must pass a release-candidate smoke test before publication, and
  ChatGPT Work web is not promised.
- Routine release evaluation stays capped at 40 model calls. The 102-case
  exhaustive path is deferred unless an official-directory or relevant
  compatibility boundary is pursued.
- Gloamere operates no plugin backend, account system, telemetry, or MCP server
  for this release.
- The earlier universal-directory ADR remains as history but no longer defines
  the `v4.0.0` release gate.
