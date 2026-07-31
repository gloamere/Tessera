# Deployment and release

Gloamere `4.0.0` is a release candidate for the repository Git marketplace at
planned immutable tag `v4.0.0`. The tag does not exist yet and remote
installation must not be described as available. The ordinary-user product is
the skills-only `gloamere-workflows@1.0.0`; `gloamere-eval@gloamere` remains a
separate maintainer tool.

The official plugin directory is an optional future distribution channel. Its
review, country selection, recording, and approval do not block the Git tag or
GitHub release. Do not claim directory availability unless a verified listing
actually exists.

## Release source

Change `release-manifest.json` first. Then run:

```bash
python scripts/generate_release_files.py
python scripts/generate_release_files.py --check
```

The generator owns `.agents/plugins/marketplace.json`, `release-index.json`,
`VERSION`, `website/app/generated-release.ts`, and each native plugin
manifest's version field. The release index and website mirror the Skill lists
and install profiles from the same source; the remaining native manifest
fields are validated against it.

For this channel, use `distributionChannel: git-marketplace` and keep
`directoryStatus: optional` with `directoryURL: null`. A future verified
listing may change the directory fields independently; it must not rewrite the
identity of the tagged Git release.

Profiles are:

- `workflows`: default, only `gloamere-workflows`;
- `maintainer`: only `gloamere-eval`;
- `complete`: Workflows plus Eval.

The wrappers expose the same selection contract: PowerShell uses
`-Profile workflows|maintainer|complete`, POSIX uses
`--profile workflows|maintainer|complete`, and `-All`/`--all` remains a
compatibility alias for `complete`.

The pinned Git selectors become valid after tag publication:
`gloamere-workflows@gloamere` and `gloamere-eval@gloamere` from
`gloamere/codex-plugins`.

Ordinary-user CLI installation after the tag is published:

```bash
codex plugin marketplace add gloamere/codex-plugins --ref v4.0.0
codex plugin add gloamere-workflows@gloamere
```

The intended targets are Codex CLI and the ChatGPT desktop plugin surface.
ChatGPT desktop compatibility is not yet verified and must pass a reproducible
smoke test against the exact release candidate before publication. ChatGPT Work
web is not part of the intended self-hosted installation surface. Before the
tag exists, testing must use an explicit local checkout such as
`./install.ps1 -Source .` or `sh install.sh --source .`.

## Static validation

```powershell
./scripts/check.ps1
```

```bash
sh scripts/check.sh
```

The check includes generated-file drift, plugin and marketplace metadata,
102-case/policy/quality contracts, unit tests, self-contained runtime checks,
and Eval inspect/lint. It makes no native model call.

Website validation:

```bash
cd website
npm ci
npm test
npm run lint
npm audit --audit-level=high
npm audit --audit-level=high --omit=dev
```

Both audits must report zero high and zero critical vulnerabilities.

## Evidence

Risk policy:

- PR: four cases per changed Skill, maximum 12;
- release: 16 base cases plus four per changed Skill, with two quality calls
  reserved per changed Skill;
- future-directory exhaustive: first run all 102 unique cases once, then retry
  only anomalies; the initial-coverage budget is 102 and the conservative hard
  cap is 120;
- output quality: one English and one Chinese golden task per changed Skill.

Routine release routing, semantic quality tasks, and targeted retries share
one hard cap of 40 model calls. The optional future-directory exhaustive path
uses its separate 120-call cap and never spends retry calls before all 102
initial cases exist in the journal.

Runner usage is documented by `scripts/run_native_eval.ps1 -?` and
`scripts/run_native_eval.sh --help`. Use `--dry-run` before spending calls,
journal every attempt, resume interrupted work, and finalize report v4 from the
journal.

The monthly drift check reuses release selection without changed-Skill
expansion:

```bash
sh scripts/run_native_eval.sh \
  --suite eval-suites/gloamere-workflows/admission-v2.json \
  --target-lock <target-lock.json> \
  --policy eval-suites/gloamere-workflows/risk-tiered-v2.json \
  --mode release --rotation-key YYYY-MM --max-calls 16
```

This 16-call monitor is drift evidence only and cannot satisfy the release
gate.

Release evidence must:

- be report schema v4 from the real Codex CLI;
- bind an evaluated commit that is HEAD or its ancestor, plus the exact current
  suite, policy, target lock, Skill hashes, model, CLI version, selection, and
  budget;
- contain an RFC 3339/ISO UTC timestamp;
- omit prompt plaintext, credentials, usernames, and absolute paths;
- have no confirmed high-risk false activation.

Report v3 is historical and never release-eligible.

The six quality tasks are reviewed semantically for evidence fidelity,
actionability, boundary compliance, and fabrication. The report stores output
and rationale hashes, not plaintext. Keyword, substring, regex, or other
automatic matches cannot authorize a release:

```bash
python scripts/validate_quality_evidence.py
python scripts/validate_quality_evidence.py --require
```

## Package preview

Dirty local work can produce an explicitly non-release preview:

```bash
python scripts/package_release.py --output-dir dist --allow-dirty
```

A real build omits `--allow-dirty` and binds CI HEAD:

```bash
python scripts/package_release.py \
  --output-dir dist \
  --expect-commit <release-commit>
```

The release asset set is:

- `gloamere-workflows-1.0.0.zip`;
- `gloamere-workflows-1.0.0.zip.sha256`;
- `gloamere-eval-1.0.0-beta.1.zip`;
- `gloamere-eval-1.0.0-beta.1.zip.sha256`;
- `release-manifest.json`;
- `release-index.json`;
- `release-provenance.json`.

Every ZIP contains `RELEASE-PROVENANCE.json`. Symlinks, submodules, untracked
sentinels, dirty tracked files, and a commit mismatch fail closed for a real
build.

## Optional directory submission

This section is dormant for the `v4.0.0` Git marketplace release. If an
official-directory submission is revived later, run:

```bash
python scripts/validate_directory_submission.py
python scripts/validate_directory_submission.py --require-complete
```

The first command validates the retained material. The complete gate also
requires:

- an eligible report-v4 entry in `release-manifest.json`;
- first-directory exhaustive evidence covering all 102 public cases, including
  adaptive anomaly rechecks;
- transparent owner-dogfood evidence from ten real tasks, with at least two
  tasks per public Skill, no confirmed high-risk false activation, and at
  least 80% needing no major rewrite;
- submission-portal confirmation that the requested `CN` availability is
  selectable and supportable;
- an HTTPS demo recording;
- the final `gloamere-workflows-1.0.0.zip`.

Upload only the Workflows ZIP and the materials under `docs/directory/`.
There is no screenshot because the plugin has no UI. None of these checks,
records, portal fields, or external approval states authorize or block the Git
marketplace release.

## Publish

1. Complete static, website, routine release evidence, and quality gates.
2. Run and record a ChatGPT desktop smoke test against the exact tracked
   release candidate: marketplace discovery, Workflows installation, all three
   Skill identities, and a fresh-task load.
3. Set `distribution.releaseStatus` in `release-manifest.json` from
   `release-candidate` to `published`; keep `directoryStatus: optional` and
   `directoryURL: null`.
4. Run `python scripts/generate_release_files.py` and the complete checks, then
   commit the exact promoted generated state on `main`.
5. Confirm `main` is synchronized and push tag `v4.0.0`. Tag CI rejects any
   commit that has not completed the `published` promotion.
6. Let release CI verify `GITHUB_SHA`, rebuild tracked-only artifacts, and
   compare provenance.
7. Publish the matching GitHub release and its generated assets; mark old
   Tessera releases legacy without deleting their tags.
8. Verify installation from the immutable tag in Codex CLI and the ChatGPT
   desktop plugin surface.

The website at `codex.gloamere.com` documents and supports the release but is
not a plugin runtime dependency.

## MCP boundary

`v4.0.0` does not enable MCP. Product Decision, Visual Review, and Knowledge
Capture work from user-provided evidence and host capabilities; they currently
need no live service data, plugin-owned authentication, or controlled remote
writes. If a validated need recurs and cannot be solved by host-native
capabilities, evaluate it as a separate version candidate. Start with a
read-only `search`/`fetch` experiment before considering authentication or
write scope, then review permissions, privacy, failure modes, maintenance, and
token cost explicitly.
