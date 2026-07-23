# Privacy

Last updated: 2026-07-23

Gloamere Eval and Gloamere Workflows are local, skill-based Codex plugins. The
plugins do not operate a Gloamere backend, create user accounts, set cookies,
collect telemetry, or transmit analytics to Gloamere.

Gloamere Eval reads the case files and project context selected by the user. It
writes JSON to stdout by default and creates a report file only when the user
explicitly supplies `--output`. Gloamere Workflows use the project files and
Codex capabilities authorized by the user. Bundled helper scripts operate
locally.

Codex and any tools, connectors, websites, or services the user separately
chooses to invoke are governed by their own privacy terms. Gloamere does not
receive that data merely because one of these plugins is installed.

Privacy questions may be raised through the public issue tracker at
<https://github.com/gloamere/codex-plugins/issues>.
