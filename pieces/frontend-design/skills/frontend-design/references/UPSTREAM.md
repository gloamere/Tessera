# Upstream provenance

- Project: [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
- Imported commit: `f8ac5e1266dba8354ea96e19994d9f4345e7ec31`
- Imported on: 2026-07-15
- License: MIT; full upstream notice is stored at `../../../LICENSE.upstream`

## Imported core

- `data/*.csv` and `data/stacks/*.csv`
- `scripts/core.py`, `design_system.py`, `search.py`, `validate_data.py`
- `scripts/tests/test_core.py`
- `references/quick-reference.md` and `pro-rules.md`

## Tessera adaptations

- Replaced the upstream broad invocation instructions with a short `frontend-design` Skill whose boundary complements `taste`.
- Added self-locating PowerShell/POSIX runners and UTF-8 handling.
- Excluded the npm CLI, installers, previews, fonts, duplicate platform assets, unrelated Skills and upstream release automation.
- Tessera owns dual-host packaging, routing cases, quality evidence and update decisions. Upstream updates are notify-only and require revalidation rather than automatic syncing.
