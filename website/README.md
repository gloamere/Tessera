# Gloamere brand site

The public information site for Gloamere's Codex-only plugins. It is built
with vinext for OpenAI Sites and has no database, authentication, analytics,
telemetry, or external font dependency.

## Routes

- `/` — product identity and release boundary
- `/eval` — Gloamere Eval contract
- `/workflows` — stable Workflows surface and provenance
- `/support` — support scope and reporting
- `/privacy` — privacy notice
- `/terms` — terms
- `/security` — security policy

Until the native admission and quality gates pass, the site must identify
`4.0.0-beta.1` as a beta candidate and must not claim that its tag is
published.

## Local validation

```bash
npm ci
npm test
npm run lint
npm audit --audit-level=high
```

Node.js 22.13 or newer is required. `npm test` builds the Cloudflare
Worker-compatible output and server-renders every public route.

`npm run build:static` produces the Caddy-ready export in `dist/client`.
The public canonical origin is `https://codex.gloamere.com`; the private Sites
deployment remains a non-canonical review surface.

`.openai/hosting.json` stores only the opaque Sites project ID and logical
storage declarations. Never add deployment credentials or runtime secrets to
the repository.
