# Gloamere Workflows

Evidence-backed workflows for product decisions, visual reviews, and durable
knowledge.

Source repository: `gloamere/codex-plugins`.

`4.0.0` is a Git marketplace release candidate. The official plugin directory
is a future optional channel and does not block the planned `v4.0.0`
repository release. The immutable tag does not exist yet, so remote
installation remains unavailable until that tag is published.

## Public product

`gloamere-workflows` serves product and design leads through three independently
routed Skills:

| Skill | Use it for |
| --- | --- |
| `gloamere-product-decision` | Compare product options from existing evidence and define scope, measures, risks, and the next validation |
| `gloamere-visual-review` | Review an existing visual artifact and prioritize evidence-based changes |
| `gloamere-knowledge-capture` | Preserve decisions, research, and operating knowledge in an existing Markdown knowledge base |

The package is skills-only: no MCP server, custom UI, external backend,
authentication, hooks, background process, or telemetry. It responds in the
user's language and is evaluated in English and Chinese. The three workflows
do not need live data, plugin-owned authentication, or controlled remote
writes, so adding MCP would increase deployment, permission, and context cost
without improving their current jobs. MCP can return only as a separately
scoped version candidate after a live-data or controlled-action need recurs,
cannot be solved by host-native capabilities, and passes a read-only
`search`/`fetch` experiment first.

The intended repository-marketplace targets are the ChatGPT desktop plugin
surface and Codex CLI. ChatGPT desktop still requires a release-candidate smoke
test before publication, so this is a target rather than a current
compatibility claim. This release does not claim that a self-hosted Git
marketplace can be installed from ChatGPT Work web, Chat, an IDE integration,
or mobile.

## Install after release

After the `v4.0.0` tag is published, install the immutable marketplace with
Codex CLI:

```bash
codex plugin marketplace add gloamere/codex-plugins --ref v4.0.0
codex plugin add gloamere-workflows@gloamere
```

If the pre-release desktop smoke test passes, the intended desktop flow after
publication is to add the Git marketplace `gloamere/codex-plugins` at tag
`v4.0.0`, install `gloamere-workflows@gloamere`, and start a new task so the
three Skills are loaded.

The repository also provides wrappers with the same pinned release default:

```powershell
./install.ps1
```

```bash
sh install.sh
```

Before the tag exists, maintainers may test an explicit local checkout without
claiming a public release:

```powershell
./install.ps1 -Source .
```

```bash
sh install.sh --source .
```

The Gloamere website and server provide documentation, support, and release
links. They are not a runtime dependency and do not receive workflow inputs.

## Maintainer tooling

`gloamere-eval@1.0.0-beta.1` remains a Git-marketplace maintainer tool for
inspecting and evaluating installed Skill routing. It is not the default
end-user product.

`gloamere-ui-system`, Debug Loop, Finance, Growth, and Internal Operations stay
under `experiments/` and are excluded from every public archive. UI System keeps
its pinned third-party notice there, but cannot return until its vendor core is
replaced and current-SHA evidence passes.

The repository release source of truth is
[`release-manifest.json`](release-manifest.json):

- distribution candidate `4.0.0`, planned tag `v4.0.0`;
- default profile `workflows`;
- maintainer profile `gloamere-eval`;
- complete profile `gloamere-workflows` plus `gloamere-eval`.

The immutable tag will expose the selectors `gloamere-workflows@gloamere` and
`gloamere-eval@gloamere` after publication. Use `-Profile maintainer` /
`--profile maintainer` only when installing Eval for repository maintenance.

## Low-token quality gate

The old 816-call `136 × 3 × 2` matrix is retired.

- Non-Skill PRs use zero model calls.
- Skill PRs select four cases per changed Skill, capped at 12.
- Release evaluation starts with 16 boundary cases, adds four per changed
  Skill, and cannot exceed 40 calls including retries.
- A future official-directory attempt may cover 102 unique routing cases once;
  only unexpected cases are repeated, under a separate 120-call hard cap.
- Monthly drift checks reuse the 16-case release baseline with a month
  rotation key and no changed-Skill expansion.
- Six bilingual golden tasks use semantic rubrics instead of substring scores.

Eval report v4 binds the exact commit, suite, risk policy, target lock, Skill
hashes, Codex CLI, model, budget, and selection. Attempts are journaled so
interrupted work can resume without rerunning completed calls.

## Develop and verify

```powershell
python -m pip install -r requirements-dev.txt
./scripts/check.ps1
cd website
npm ci
npm test
npm run lint
npm audit --audit-level=high
npm audit --audit-level=high --omit=dev
```

POSIX:

```bash
python3 -m pip install -r requirements-dev.txt
sh scripts/check.sh
```

Useful non-model checks:

```bash
python scripts/validate_directory_submission.py
python scripts/validate_release_evidence.py
python scripts/validate_quality_evidence.py
python scripts/package_release.py --output-dir dist --allow-dirty
```

The last command creates a non-release-eligible local preview when tracked
files are dirty. A real release build rejects dirty tracked files, packages
only Git-tracked regular blobs, embeds commit/content provenance, and emits
`release-provenance.json`.

## Release state

The Git marketplace release requires eligible report-v4 evidence for the final
protected content identity, six-case semantic output-quality evidence without
critical regression, static checks, website checks, and a tracked-only package
bound to the release commit. It also requires a reproducible ChatGPT desktop
smoke test of the exact release candidate before publication. It does not
require an official-directory review, country selection, directory demo, or
participant-count gate.

The owner dogfood record remains useful product evidence but is not a release
blocker. The 102-case exhaustive run and materials under `docs/directory/` are
required only if an official-directory submission is revived later.

See [optional directory materials](docs/directory/README.md),
[deployment](docs/DEPLOYMENT.md), [architecture](docs/ARCHITECTURE.md),
[accepted distribution decision](docs/decisions/git-marketplace-v4-release.md),
[migration](MIGRATION.md), [support](SUPPORT.md),
[security](SECURITY.md), [privacy](docs/PRIVACY.md), and
[terms](docs/TERMS.md).

## License

[MIT](LICENSE) © 2026 Gloamere
