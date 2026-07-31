# Optional future official-directory submission

This directory retains a reviewable template for a possible future
`gloamere-workflows@1.0.0` skills-only submission. It is not part of the
`v4.0.0` Git marketplace release gate. The repository tag, GitHub release, and
self-hosted installation path do not wait for any portal field, country
selection, recording, exhaustive run, or external approval stored here.

If the official-directory channel is revived:

1. Run the repository checks, both website audits, and the package dry run.
2. Produce eligible report-v4 routing evidence bound to a current protected
   identity (evaluated commit, suite, policy, model, CLI, and Skill hashes).
3. Review all six bilingual quality outputs against `quality-v1.json`, register
   the hashed semantic report, and run
   `python scripts/validate_quality_evidence.py --require`.
4. Complete the transparent owner-dogfood record for ten real tasks, with at
   least two tasks for each public Skill and at least 80% needing no major
   rewrite. This is an internal value gate, not an OpenAI participant-count
   requirement.
5. Confirm that the requested `CN` availability is selectable in the
   submission portal, then replace the pending availability and
   demo-recording values in `submission.json`.
6. Confirm the ZIP contains three Skills, no MCP/app configuration, and no
   screenshot declaration.

Until that decision, `submission.json` is a non-authoritative draft and its
pending values are expected. The submission portal, not this JSON file, is the
final system of record.
Current requirements are documented in the official
[submission guide](https://developers.openai.com/plugins/deploy/submission)
and [plugin guidelines](https://developers.openai.com/plugins/app-guidelines).
