# Gloamere Codex Plugins

Evidence-led evaluation and focused professional workflows for Codex.

> `4.0.0-beta.1` is a Beta candidate with a planned
> `v4.0.0-beta.1` tag; it has not been published. The tag workflow will refuse
> to publish until current native evidence passes the release gate. The
> repository, marketplace, plugin IDs, and installation commands changed from
> the 3.x legacy installation. Read [MIGRATION.md](MIGRATION.md) before
> upgrading.

## Plugins

| Plugin | Bundled skills | Purpose |
| --- | --- | --- |
| `gloamere-eval` | `gloamere-skill-eval` | Inspect, lint, and evaluate Codex skill routing while distinguishing observable evidence from model claims |
| `gloamere-workflows` | `gloamere-ui-system`, `gloamere-visual-review`, `gloamere-knowledge-capture`, `gloamere-product-decision` | Opt-in UI, visual review, knowledge capture, and product-decision workflows |

Both plugins are Codex-only, self-contained, and installed independently.
They do not add hooks, MCP servers, background processes, telemetry, or a
second task-routing layer. Codex remains responsible for skill discovery,
planning, confirmation, delegation, and plugin lifecycle.

## Planned pinned-beta installation

The commands below become valid only after `v4.0.0-beta.1` passes the release
gate and is published. They intentionally target the immutable tag, never
`main`.

Windows PowerShell installs `gloamere-eval`:

```powershell
irm https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.ps1 | iex
```

Install both plugins:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.ps1))) -All
```

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.sh | sh
curl -fsSL https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.sh | sh -s -- --all
```

`release-manifest.json` names these profiles `eval` (the default) and
`complete` (`-All` / `--all`). Both published plugins currently have `beta`
maturity.

The equivalent manual installation is:

```bash
codex plugin marketplace add gloamere/codex-plugins --ref v4.0.0-beta.1
codex plugin add gloamere-eval@gloamere
codex plugin add gloamere-workflows@gloamere
codex plugin list --json
```

The installers use only native Codex plugin commands. If a 3.x legacy selector
is present, they stop before changing anything and print the manual
“remove old plugin → remove old marketplace → rerun Gloamere install” sequence.
They never remove, disable, or modify a legacy installation themselves.

## Use

Example prompts:

- “Use Gloamere Eval to inspect this repository’s Codex skill-routing surface.”
- “Run a native Gloamere Eval check and explain the evidence level.”
- “Use Gloamere Workflows to define a coherent UI system for this product.”
- “Capture this product decision as a durable, linked project record.”

The Eval runtime uses the Python 3.10+ standard library, inspects the plugins
actually installed by the user, and writes requested reports to the selected
location. It does not ship a business-specific benchmark suite. Workflows load
only when their descriptions match the task; installing the bundle does not
load all four skills on every turn.

## Develop and verify

```powershell
python -m pip install -r requirements-dev.txt
./scripts/check.ps1
python scripts/validate_release_evidence.py
```

On macOS or Linux:

```bash
python3 -m pip install -r requirements-dev.txt
sh scripts/check.sh
python3 scripts/validate_release_evidence.py
```

The same check surface runs on Ubuntu, macOS, and Windows, with Python
3.10–3.14 coverage and launcher smoke tests in Windows PowerShell 5.1 and
PowerShell 7. The platform matrix pins Codex CLI `0.145.0`; Windows also
exercises first install, repeat install, upgrade, disable/enable, uninstall,
and detect-only 3.x migration in an isolated `CODEX_HOME`. A tagged release
also builds one deterministic ZIP and SHA-256 sidecar for each plugin.

`release-manifest.json` is the release source of truth, including plugin
maturity and the `eval` / `complete` installation profiles.
`scripts/generate_release_files.py` derives the Codex marketplace and
`release-index.json`; CI runs it with `--check`. `VERSION`, plugin manifests,
installer defaults, archive names, and the Git tag are checked mirrors. Never
publish installers from `main`; use the immutable tag.

The ordinary evidence check reports `pending` without failing while native
reports are absent. A tag release runs
`python scripts/validate_release_evidence.py --require`; fixture adapters,
prompt plaintext, stale target identities, incomplete batches, and metrics
below the manifest thresholds block publication.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment and release](docs/DEPLOYMENT.md)
- [Generated release index](release-index.json)
- [v4 migration](MIGRATION.md)
- [v4 architecture decision](docs/decisions/codex-only-v4-release.md)
- [Workflows provenance and third-party boundary](plugins/gloamere-workflows/PROVENANCE.md)
- [Support](SUPPORT.md)
- [Security](SECURITY.md)
- [Privacy](docs/PRIVACY.md)
- [Terms](docs/TERMS.md)

Historical ADRs and evaluation evidence remain in the repository for
traceability. They do not define the current public release surface.

## License

[MIT](LICENSE) © 2026 Gloamere
