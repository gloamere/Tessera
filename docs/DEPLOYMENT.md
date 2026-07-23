# Deployment and release

Gloamere 4.x distributes two Codex plugins from
`gloamere/codex-plugins`. Version `4.0.0-beta.1` is currently a Beta candidate
for the planned `v4.0.0-beta.1` tag; the tag has not been published. After the
release gate passes, both installation and release assets will be pinned to
that immutable tag.
`release-manifest.json` is authoritative for plugin maturity and installation
profiles: `eval` is the default and `complete` is selected by `-All` /
`--all`. Both plugins have `beta` maturity in this release.

## User installation

The following commands are planned interfaces. They work only after
`v4.0.0-beta.1` passes the native-evidence gate and is published; do not replace
the tag with `main`.

PowerShell:

```powershell
# Eval only
irm https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.ps1 | iex

# Eval and Workflows
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.ps1))) -All
```

POSIX shell:

```bash
# Eval only
curl -fsSL https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.sh | sh

# Eval and Workflows
curl -fsSL https://raw.githubusercontent.com/gloamere/codex-plugins/v4.0.0-beta.1/install.sh | sh -s -- --all
```

Manual equivalent:

```bash
codex plugin marketplace add gloamere/codex-plugins --ref v4.0.0-beta.1
codex plugin add gloamere-eval@gloamere
codex plugin add gloamere-workflows@gloamere
codex plugin list --json
```

The installer does not clone the repository, install Python packages, edit
`config.toml`, or remove existing plugins. It performs a read-only
`codex plugin list --json` before installation. If a 3.x legacy selector is
present, it links [MIGRATION.md](../MIGRATION.md), prints the manual migration
sequence, and stops before adding a marketplace or plugin.

Start a new Codex task after installation so the skill catalog refreshes.

## Installed contents

`gloamere-eval` includes its runner, contract schemas, PowerShell and POSIX
wrappers, and brand assets. Running Eval requires a callable Python 3.10+
interpreter but no third-party Python package. It does not publish a fixed
business benchmark: maintainers generate a target lock from the installed
plugins and supply a suite bound to those real targets.

`gloamere-workflows` includes four skills:

- `gloamere-ui-system`
- `gloamere-visual-review`
- `gloamere-knowledge-capture`
- `gloamere-product-decision`

The UI skill bundles local design reference data and standard-library helper
scripts. The other skills are instruction-first. Neither plugin contains hooks,
MCP servers, background services, or telemetry.

## Maintainer validation

```powershell
python -m pip install -r requirements-dev.txt
./scripts/check.ps1
```

```bash
python3 -m pip install -r requirements-dev.txt
sh scripts/check.sh
```

Checks run on Ubuntu, macOS, and Windows. Ubuntu covers Python 3.10–3.14,
all three platforms run Python 3.12, and Windows separately smokes the Eval
launcher in Windows PowerShell 5.1 and PowerShell 7. The platform matrix pins
Codex CLI `0.145.0`; its Windows job runs the native plugin manager in an
isolated `CODEX_HOME`. Checks cover:

1. release-manifest, VERSION, marketplace, and plugin-manifest consistency;
2. public metadata, legal links, and bundled brand assets;
3. exact plugin and skill sets;
4. installer syntax, fixed-tag defaults, and read-only legacy detection;
5. first install, repeat install, `beta.0 → beta.1` upgrade, disable/enable,
   uninstall, and detect-only 3.x migration;
6. unit tests and fixture-backed Eval behavior;
7. self-contained archive construction and SHA-256 verification.

Real native Eval runs require a signed-in Codex environment and are intentionally
separate from fixture-based CI.

The release manifest binds the Workflows admission suite, repeat and independent
batch counts, metric thresholds, current Skill SHA-256 values, and an initially
empty report list. The ordinary command is non-blocking while evidence is still
being collected:

```bash
python scripts/validate_release_evidence.py
```

Before tagging, each report entry must name a real report v3 path, the report
file SHA-256, and its target-lock SHA-256. Reports must come from the Codex CLI,
omit prompt plaintext and absolute paths, cover the full suite for both batches,
and bind the enabled plugin version, Skill files, plugin manifest, and
`agents/openai.yaml` assets. Synthetic and fixture-adapter reports are never
release evidence.

## Cut a release

1. Update `release-manifest.json`.
2. Run `python scripts/generate_release_files.py` to regenerate the marketplace
   and `release-index.json`.
3. Mirror its distribution version to `VERSION`, plugin versions to both
   manifests, and its tag to both installers and public documentation.
4. Run the complete check locally.
5. Run `python scripts/validate_release_evidence.py --require`. Do not create
   the tag while the result is `pending` or `fail`.
6. Create and push the exact tag declared by the release manifest.
7. The release workflow repeats all checks on three operating systems, runs the
   brand-site test/lint/security audit, and requires the evidence gate again.
8. The packaging job creates:

   - `gloamere-eval-1.0.0-beta.1.zip`
   - `gloamere-eval-1.0.0-beta.1.zip.sha256`
   - `gloamere-workflows-1.0.0-beta.1.zip`
   - `gloamere-workflows-1.0.0-beta.1.zip.sha256`
   - `release-manifest.json`
   - `release-index.json`

9. GitHub Release receives the two plugin archives, their checksum sidecars,
   the authoritative manifest, and the generated download index.

`scripts/package_release.py` normalizes ZIP timestamps and file modes so the
same source tree produces stable archives.

## Upgrade and rollback

Treat every beta tag as immutable. Review release notes and change the tracked
marketplace ref only to a published tag; never point production installation
instructions at `main`.

Gloamere does not automatically remove or rewrite legacy installations. Follow
[MIGRATION.md](../MIGRATION.md) to inspect selectors, install the replacement,
verify it in a new task, and then decide whether to remove the old plugin with
Codex’s native plugin manager.
