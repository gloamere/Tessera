# Owner dogfood validation

This is optional product-learning evidence for the Git marketplace release. It
becomes a submission gate only if the official-directory channel is revived.

This project currently has one real user, so the internal value gate uses
transparent owner dogfooding instead of inventing external pilot
participants. OpenAI's
[submission guide](https://developers.openai.com/plugins/deploy/submission)
requires the separate set of five positive and three negative reproducible
test cases; it does not require five pilot participants.

Record only non-sensitive outcomes from real work. Existing tasks may be
included when their outcome can still be reconstructed honestly:

| Task ID | Date | Skill | Language | Task outcome | Major rewrite required | Minutes of rework | Failure category |
| --- | --- | --- | --- | --- | --- | ---: | --- |

Suggested acceptance for a future directory submission:

- one maintainer using the plugin for at least 10 completed real tasks;
- at least two tasks for each of the three public Skills;
- at least 80% proceed without a major rewrite;
- no confirmed high-risk false activation;
- every failure is mapped to routing, evidence fidelity, actionability,
  boundary compliance, fabrication, or infrastructure.

This evidence can detect workflow and usability regressions, but it does not
establish independent demand or broad user satisfaction. Keep that limitation
in the submission notes. After recording the tasks, update `completedTasks`,
`majorRewriteTasks`, `readyWithoutMajorRewriteRate`, `skillTaskCounts`, and
`confirmedHighRiskFalseActivations` in `submission.json`; set the status to
`complete` only when the aggregates meet every rule above. Do not commit
customer content, screenshots, raw conversations, or other sensitive data;
commit only aggregate, redacted results.
