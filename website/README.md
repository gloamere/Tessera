# Gloamere Workflows brand site

The public information and support site for the Gloamere Workflows Git
marketplace release. It is built with vinext and has no database,
authentication, analytics, telemetry, or external font dependency.

## Routes

- `/` — Workflows product identity and Git marketplace status
- `/workflows` — the three public workflow Skills
- `/support` — release status, supported surfaces, and reporting
- `/privacy` — privacy notice
- `/terms` — terms
- `/security` — security policy

`/eval` is retained as a non-indexed maintainer reference. It is not part of
the ordinary-user navigation.

Before `v4.0.0` is tagged, the site shows only explicit local-checkout preview
commands and must not render the nonexistent remote tag command. After
publication, the immutable Git tag becomes the ordinary-user distribution
source. The official directory remains a future option and does not block this
release.

The intended self-hosted targets are the ChatGPT desktop plugin surface and
Codex CLI. ChatGPT desktop remains a pre-release smoke-test requirement rather
than a current compatibility claim. The site does not promise a self-hosted
installation path on ChatGPT Work web.

## Local validation

```bash
npm ci
npm test
npm run lint
npm audit --audit-level=high
npm audit --audit-level=high --omit=dev
```

Node.js 22.13 or newer is required. `npm test` builds the Cloudflare
Worker-compatible output and server-renders every public route.

`npm run build:static` produces the Caddy-ready export in `dist/client`.
The public canonical origin is `https://codex.gloamere.com`; the private Sites
deployment remains a non-canonical review surface.

`.openai/hosting.json` stores only the opaque Sites project ID and logical
storage declarations. Never add deployment credentials or runtime secrets to
the repository.
