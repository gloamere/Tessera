# Migrate from Tessera to Gloamere 4

Gloamere 4 replaces the Tessera namespace and separates the public professional
workflow product from maintainer evaluation tooling.

| Before 4.0 | Gloamere 4 |
| --- | --- |
| Repository `gloamere/Tessera` | `gloamere/codex-plugins` |
| Marketplace `tessera` | Maintainer marketplace `gloamere` |
| `tessera-core@tessera` | Maintainer-only `gloamere-eval@gloamere` |
| Separate UI, review, knowledge, and product plugins | Directory package `gloamere-workflows@1.0.0` |
| Distribution 3.x | Submission candidate `4.0.0`, planned tag `v4.0.0` |

The public Workflows package contains Product Decision, Visual Review, and
Knowledge Capture. UI System is incubated under `experiments/` and has no
automatic replacement in this release.

## Safe migration

1. Inspect the current installation with `codex plugin list --json`.
2. Preserve local reports and project files; plugin removal does not authorize
   deleting them.
3. Remove legacy plugins and the old marketplace only when you choose:

   ```bash
   codex plugin remove <plugin>@tessera
   codex plugin marketplace remove tessera
   ```

4. After directory publication, install Gloamere Workflows from its directory
   listing. Maintainers may separately install Eval from the immutable
   `v4.0.0` Git marketplace after that tag exists.
5. Start a new task and verify the exact plugin version, enabled state, and
   three public Skill IDs.

The repository installers stop before changing anything when they detect an
old `@tessera` plugin. They never remove, disable, migrate, or rewrite a legacy
installation.

## Eval evidence

Keep report v3 and older files as historical evidence. Only report v4 can
qualify a 4.0 release because it binds the risk policy, selection, budget,
commit, model, CLI, suite, target lock, and current Skill hashes.

## Rollback

Removing a Gloamere plugin does not restore or alter an old installation. If an
old plugin was retained, use the host's native plugin manager to re-enable it.
Local project files and prior evaluation results remain user-controlled.
