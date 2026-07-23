# Upstream provenance

- Project: [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
- Imported commit: `f8ac5e1266dba8354ea96e19994d9f4345e7ec31`
- Imported on: 2026-07-15
- License: MIT
- Full notice: `../../../THIRD_PARTY_NOTICES/next-level-builder-MIT.txt`

## Vendored material

- `data/*.csv` and `data/stacks/*.csv`
- `scripts/core.py`, `design_system.py`, `search.py`, `validate_data.py`
- `scripts/tests/test_core.py`
- `references/quick-reference.md` and `pro-rules.md`

The CSV files remain byte-for-byte copies of the pinned import. The Python logic
is unchanged except for one host-specific docstring made host-neutral for the
Codex-only package. Changes to vendored material require a provenance update,
license review, and regression validation.

## Gloamere orchestration

- `SKILL.md` provides the original Gloamere routing boundary and workflow under the unique ID `gloamere-ui-system`.
- PowerShell and POSIX wrappers locate `search.py` relative to their own directory and enable UTF-8 output.
- The Skill resolves all resources from its own installed root; it does not depend on the repository layout or another global UI Skill.
- Excluded the npm CLI, installers, previews, fonts, duplicate platform assets, unrelated Skills and upstream release automation.
- Upstream updates are reviewed manually and are never synchronized automatically.
