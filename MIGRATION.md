# Migrate to Gloamere 4.x

Gloamere 4.x is a Codex-only product and package reset. It uses a new repository,
marketplace name, plugin IDs, skill names, and version line.

| Before 4.0 | Gloamere 4.x |
| --- | --- |
| Repository `gloamere/Tessera` | `gloamere/codex-plugins` |
| Marketplace `tessera` | `gloamere` |
| `tessera-core@tessera` | `gloamere-eval@gloamere` |
| Separate frontend, visual-review, knowledge, and product plugins | `gloamere-workflows@gloamere` |
| Distribution 3.x | Distribution `4.0.0-beta.1` |
| Plugin versions followed the distribution | Both public plugins start at `1.0.0-beta.1` |

Finance, growth, and general business-operations skills are not part of the v4
public beta. Existing installations remain untouched; use Codex native
capabilities or another explicitly installed workflow if those domains are
needed.

## Safe migration

1. Inspect current plugins without changing them:

   ```bash
   codex plugin list --json
   ```

2. Preserve any local reports or project files you want to keep. Plugin removal
   does not authorize deleting those files.
3. Remove each legacy plugin reported by the installer, then remove the legacy
   marketplace:

   ```bash
   codex plugin remove <plugin>@tessera
   codex plugin marketplace remove tessera
   ```

4. Install the pinned v4 marketplace and the desired replacement:

   ```bash
   codex plugin marketplace add gloamere/codex-plugins --ref v4.0.0-beta.1
   codex plugin add gloamere-eval@gloamere
   codex plugin add gloamere-workflows@gloamere
   ```

5. Start a new task and verify the exact plugin versions, enabled states, and
   new Skill names.

The v4 installers intentionally stop before making changes when they detect an
old `@tessera` plugin. They print the removal sequence but never execute it,
disable a plugin, delete local reports, or clean legacy data. If a side-by-side
comparison is necessary, use a separate `CODEX_HOME`; duplicate descriptions in
one live catalog can create identity conflicts and are not a valid final
routing baseline.

## Eval report compatibility

Keep pre-v4 reports as historical evidence. Do not append new output to an old
report or compare fields without checking its schema version. Generate a fresh
v4 baseline after installation.

## Rollback

Removing a Gloamere v4 plugin does not restore or alter an old installation.
If an old plugin was retained, it can be re-enabled through Codex’s native
plugin manager. Local project files and prior `eval-results/` remain
user-controlled.
