# Deployment and release

Gloamere `4.0.0` is an unpublished submission candidate for planned tag
`v4.0.0`. The ordinary user product is the skills-only
`gloamere-workflows@1.0.0` directory artifact. The Git marketplace also retains
`gloamere-eval@gloamere` for maintainers; it is not submitted to the directory.

Do not publish an installation command, mark a GitHub release latest, or claim
directory availability before external approval.

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

Directory state is fail-closed. Keep `directoryURL: null` while
`directoryStatus` is `preparing` or `submitted`. Only after the verified
listing is live, set `directoryStatus: approved` and store its HTTPS URL in
`directoryURL`; the website will then expose that link. Set `releaseStatus:
published` only after directory approval and the matching repository release.

Profiles are:

- `workflows`: default, only `gloamere-workflows`;
- `maintainer`: only `gloamere-eval`;
- `complete`: Workflows plus Eval.

The wrappers expose the same selection contract: PowerShell uses
`-Profile workflows|maintainer|complete`, POSIX uses
`--profile workflows|maintainer|complete`, and `-All`/`--all` remains a
compatibility alias for `complete`.

The pinned Git selectors become valid only after tag publication:
`gloamere-workflows@gloamere` and `gloamere-eval@gloamere` from
`gloamere/codex-plugins`. Public Workflows installation should still point to
the approved directory listing rather than the maintainer installer.

## Static validation

```powershell
./scripts/check.ps1
```

```bash
sh scripts/check.sh
```

The check includes generated-file drift, plugin and directory metadata,
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
- exhaustive: first run all 102 unique cases once, then retry only anomalies;
  the initial-coverage budget is 102 and the conservative hard cap is 120;
- output quality: one English and one Chinese golden task per changed Skill.

Routine release routing, semantic quality tasks, and targeted retries share
one hard cap of 40 model calls. The one-time exhaustive path uses its separate
120-call cap and never spends retry calls before all 102 initial cases exist in
the journal.

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

## Directory submission

Run:

```bash
python scripts/validate_directory_submission.py
python scripts/validate_directory_submission.py --require-complete
```

The first command validates the local structure. The complete gate also
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
There is no screenshot because the plugin has no UI.

## Publish

1. Complete all static, website, evidence, pilot, and directory gates.
2. Commit the exact generated state on `main`.
3. Confirm `main` is synchronized and push tag `v4.0.0`.
4. Let release CI verify `GITHUB_SHA`, rebuild tracked-only artifacts, and
   compare provenance.
5. Upload the Workflows ZIP in the official submission portal.
6. After approval, publish the directory listing and then mark the matching
   GitHub release current; mark old Tessera releases legacy without deleting
   their tags.

Approval and publication are external states. Repository completion cannot
claim them early.
