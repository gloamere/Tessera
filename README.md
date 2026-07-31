# Gloamere Workflows

Evidence-backed workflows for product decisions, visual reviews, and durable
knowledge.

Source repository: `gloamere/codex-plugins`.

> `4.0.0` is an unpublished submission candidate. The public
> `gloamere-workflows@1.0.0` package is being prepared for the universal plugin
> directory; no installation command or `v4.0.0` tag is valid yet.

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
user's language and is evaluated in English and Chinese.

Public plugins from the universal directory are supported on ChatGPT Work web,
the ChatGPT Work and Codex desktop apps, and the Codex CLI plugin browser.
Plugins are not supported in Chat, the IDE extension, mobile, or other hosts.

## Maintainer tooling

`gloamere-eval@1.0.0-beta.1` remains a Git-marketplace maintainer tool for
inspecting and evaluating installed Skill routing. It is not the default
end-user product and is not included in the first directory submission.

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

After approval and publication, immutable tag installation may expose the
selectors `gloamere-workflows@gloamere` and `gloamere-eval@gloamere`. Until
then, use a local checkout only for maintainer testing.

## Low-token quality gate

The old 816-call `136 × 3 × 2` matrix is retired.

- Non-Skill PRs use zero model calls.
- Skill PRs select four cases per changed Skill, capped at 12.
- Release evaluation starts with 16 boundary cases, adds four per changed
  Skill, and cannot exceed 40 calls including retries.
- The initial directory review first covers 102 unique routing cases once;
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

The following external prerequisites are intentionally still pending:

- eligible report-v4 evidence for the final protected content identity;
- six-case semantic output-quality evidence without critical regression;
- one maintainer's transparent dogfood evidence from ten real tasks, covering
  every public Skill and reaching the 80% no-major-rewrite threshold;
- submission-portal confirmation that the requested `CN` availability is
  selectable and supportable;
- an HTTPS demo recording;
- directory review and approval.

See [directory submission materials](docs/directory/README.md),
[deployment](docs/DEPLOYMENT.md), [architecture](docs/ARCHITECTURE.md),
[accepted product decision](docs/decisions/universal-workflows-v4-release.md),
[migration](MIGRATION.md), [support](SUPPORT.md),
[security](SECURITY.md), [privacy](docs/PRIVACY.md), and
[terms](docs/TERMS.md).

## License

[MIT](LICENSE) © 2026 Gloamere
