# Official directory submission

This directory is the reviewable source for the `gloamere-workflows@1.0.0`
skills-only submission. The upload artifact is
`dist/gloamere-workflows-1.0.0.zip`; `gloamere-eval` and every workflow under
`experiments/` are excluded.

Before upload:

1. Run the repository checks, both website audits, and the package dry run.
2. Produce eligible report-v4 routing evidence bound to a current protected
   identity (evaluated commit, suite, policy, model, CLI, and Skill hashes).
3. Review all six bilingual quality outputs against `quality-v1.json`, register
   the hashed semantic report, and run
   `python scripts/validate_quality_evidence.py --require`.
4. Complete the pilot record for at least five product/design leads and ten
   real tasks.
5. Replace the pending country availability and demo-recording values in
   `submission.json`.
6. Confirm the ZIP contains three Skills, no MCP/app configuration, and no
   screenshot declaration.

The submission portal, not this JSON file, is the final system of record.
Current requirements are documented in the official
[submission guide](https://developers.openai.com/plugins/deploy/submission)
and [plugin guidelines](https://developers.openai.com/plugins/app-guidelines).
