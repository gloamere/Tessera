# Support

Gloamere `4.0.0` is a Git marketplace release candidate. Remote installation
and ordinary-user support begin only after the immutable `v4.0.0` tag is
published and the release checks pass; official-directory approval is not a
prerequisite.

The intended Workflows targets are the ChatGPT desktop plugin surface and Codex
CLI. ChatGPT desktop compatibility remains a pre-release smoke-test gate, not a
current support claim. This release does not claim a self-hosted installation
path on ChatGPT Work web, Chat, the IDE extension, or mobile.
`gloamere-eval` additionally requires local Codex CLI execution and Python
3.10+.

Before opening a report:

1. record the plugin version, surface, operating system, and Codex version;
2. reproduce in a new task;
3. for CLI installations, run `codex plugin list --json`;
4. remove secrets, prompt contents, usernames, and absolute paths;
5. include the smallest safe reproduction and evidence status.

Use the [public issue tracker](https://github.com/gloamere/codex-plugins/issues)
for installation problems, reproducible bugs, documentation gaps, and feature
requests. Do not label an `unobservable` or infrastructure result as a routing
failure.

Security vulnerabilities must not be posted publicly. Follow
[SECURITY.md](SECURITY.md). Experimental workflows, modified forks, old plugin
identities, unsupported clients, and unpublished candidates have no public
support commitment.
