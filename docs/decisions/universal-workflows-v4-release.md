---
status: superseded
superseded_by: git-marketplace-v4-release
date: 2026-07-31
decision-makers: Gloamere maintainers
---

# Gloamere 4 adopts a universal three-workflow product

## Context

The prior candidate combined a developer Eval product with four professional
workflows, defaulted installation to Eval, relied on an unpublished Git tag,
and required 816 model calls for every release. UI System also contained a
third-party vendor core that the repository already identified as an
official-directory blocker.

OpenAI now publishes skills-only plugins through one universal directory shared
by supported ChatGPT and Codex surfaces. A no-UI skills package must not submit
screenshots and must provide a focused listing, starter prompts, and positive
and negative review cases.

## Decision

Gloamere Workflows (`gloamere-workflows`) is the public product for product and
design leads. Version `1.0.0` contains exactly:

- `gloamere-product-decision`;
- `gloamere-visual-review`;
- `gloamere-knowledge-capture`.

The package is skills-only and bilingual, with no MCP server, custom UI,
backend, authentication, hooks, or telemetry. UI System moves intact to
`experiments/` until its vendor core is replaced. `gloamere-eval` remains a
separate, maintainer-only Git-marketplace tool; Debug Loop remains experimental.

Distribution `4.0.0` is a submission candidate for tag `v4.0.0`. The directory
package uses version `1.0.0`; Eval remains `1.0.0-beta.1`.

The release gate adopts `risk-tiered-v2`: non-Skill PRs use zero model calls,
Skill PRs are capped at 12, routine release evidence is capped at 40, and the
102-case exhaustive suite runs only for initial submission or a relevant
compatibility change. Exhaustive first completes every unique case once, then
rechecks only anomalies under a separate 120-call hard cap. Report v4 binds the
exact selection, budget, policy, commit, model, CLI, suite, target lock, and
Skill hashes, with resumable attempt journals.

Release archives contain only Git-tracked regular files and embed commit and
content provenance. The website, marketplace, version file, and release index
are deterministic projections of `release-manifest.json`.

## Consequences

- Ordinary users see one coherent Decide → Review → Record product.
- The first directory package has no third-party runtime material.
- Eval can evolve without dominating public Workflows positioning.
- Repeated prompts no longer consume hundreds of calls without adding boundary
  coverage.
- Directory publication remains blocked on eligible evidence, pilot results,
  country availability, demo recording, and external review.
- The superseded Codex-only two-plugin ADR remains available for history.
