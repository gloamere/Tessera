# Gloamere Workflows brand site

The public information site for the Gloamere Workflows official-directory
candidate. It is built with vinext for OpenAI Sites and has no database,
authentication, analytics, telemetry, or external font dependency.

## Routes

- `/` — Workflows product identity and directory status
- `/workflows` — the three public workflow Skills
- `/support` — directory status, supported surfaces, and reporting
- `/privacy` — privacy notice
- `/terms` — terms
- `/security` — security policy

`/eval` is retained as a non-indexed maintainer reference. It is not part of
the ordinary-user navigation or the first directory submission.

Until the official review is approved and its verified directory listing is
live, the site must identify Gloamere Workflows as a submission candidate and
must not publish installation commands.

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
