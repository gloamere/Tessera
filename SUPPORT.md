# Support

Gloamere 4.0 is a public beta. Support covers the current tagged release of
`gloamere-eval` and `gloamere-workflows` on Codex App, CLI, and IDE. Eval 4.0
supports local Codex CLI execution only.

Before opening a report:

1. confirm the exact Gloamere tag, plugin version, Codex version, operating
   system, and Python version when Eval is involved;
2. reproduce in a new Codex task;
3. run `codex plugin list --json` and check that the intended plugin is
   installed and enabled;
4. remove secrets, prompt contents, usernames, and absolute local paths from
   logs or reports.

Use the
[public issue tracker](https://github.com/gloamere/codex-plugins/issues) for
installation problems, reproducible bugs, documentation gaps, and feature
requests. Include the smallest safe reproduction and the relevant
`evidence_status`; do not label an `unobservable` result as a routing failure.

Security vulnerabilities should not be posted publicly. Follow
[SECURITY.md](SECURITY.md) instead.

Gloamere does not provide support for unpublished experimental workflows,
modified forks, old plugin identities, or compatibility with non-Codex hosts.
