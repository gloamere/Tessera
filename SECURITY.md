# Security policy

## Supported versions

During the public beta, security fixes target the latest published Gloamere 4.x
tag. Historical 3.x artifacts are retained for traceability but are not an
active compatibility or security-support surface.

## Report a vulnerability

Please use
[GitHub private vulnerability reporting](https://github.com/gloamere/codex-plugins/security/advisories/new).
Do not open a public issue for a suspected vulnerability.

Include the affected plugin and version, Codex/Python/OS versions, impact,
reproduction steps, and a minimal proof of concept. Remove API keys, tokens,
private prompts, personal paths, and customer data. Gloamere will acknowledge
the report through GitHub and coordinate disclosure after a fix is available;
the beta does not promise a fixed response-time SLA.

## Security boundary

The published plugins contain no Gloamere backend, telemetry, hooks, MCP
servers, or background services. They still operate within the permissions and
tools granted to Codex. Users should review requested actions, protect local
inputs, and install only immutable tagged releases whose checksums match the
published SHA-256 sidecars.

Gloamere Eval treats missing, malformed, truncated, or unknown host evidence as
non-verified. A model statement is not proof that a Skill was loaded.
