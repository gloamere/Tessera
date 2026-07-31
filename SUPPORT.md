# Support

Gloamere `4.0.0` is an unpublished submission candidate. Public Workflows
support begins only after the universal-directory listing is approved and
published.

The supported public surfaces are ChatGPT Work on the web, ChatGPT Work and
Codex in the desktop app, and the Codex CLI plugin browser. Plugins are not
available in Chat, the IDE extension, or mobile. `gloamere-eval` additionally
requires local Codex CLI execution and Python 3.10+.

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
