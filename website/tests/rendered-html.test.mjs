import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set(
    "test",
    `${process.pid}-${Date.now()}-${pathname.replaceAll("/", "-")}`,
  );
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

const routes = [
  ["/", /Evidence-led Codex plugins/],
  ["/eval", /Gloamere Eval/],
  ["/workflows", /Gloamere Workflows/],
  ["/support", /Support/],
  ["/privacy", /Privacy/],
  ["/terms", /Terms/],
  ["/security", /Security/],
];

test("server-renders every public route with the shared brand shell", async () => {
  for (const [pathname, titlePattern] of routes) {
    const response = await render(pathname);
    assert.equal(response.status, 200, pathname);
    assert.match(
      response.headers.get("content-type") ?? "",
      /^text\/html\b/i,
      pathname,
    );

    const html = await response.text();
    assert.match(html, titlePattern, pathname);
    assert.match(html, /Gloamere/, pathname);
    assert.match(html, /Skip to content/, pathname);
    assert.match(html, /Language \/ 语言/, pathname);
    assert.match(html, /href="\/privacy"/, pathname);
    assert.match(html, /href="\/security"/, pathname);
    assert.match(html, /property="og:image" content="https?:\/\/[^"]+\/og\.png"/i);
    assert.match(
      html,
      new RegExp(
        `rel="canonical" href="https://codex\\.gloamere\\.com${
          pathname === "/" ? "/" : pathname
        }"`,
      ),
      pathname,
    );
    assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i, pathname);
  }
});

test("home and plugin routes state the release and evidence boundaries", async () => {
  const [home, evalPage, workflows] = await Promise.all([
    render("/").then((response) => response.text()),
    render("/eval").then((response) => response.text()),
    render("/workflows").then((response) => response.text()),
  ]);

  assert.match(home, /v4\.0\.0-beta\.1/);
  assert.match(home, /prompt_sha256/);
  assert.match(home, /manifest \/ Skill \/ agent SHA/);
  assert.match(home, /evidence_status/);
  assert.match(home, /not a published native-admission result/i);
  assert.match(home, /codex plugin add gloamere-eval@gloamere/);
  assert.match(home, /codex plugin add gloamere-workflows@gloamere/);

  assert.match(evalPage, /unobservable/);
  assert.match(evalPage, /identity_conflict/);
  assert.match(evalPage, /verdict = null/);
  assert.match(evalPage, /does not claim.*official native-admission/is);

  for (const skill of [
    "gloamere-ui-system",
    "gloamere-visual-review",
    "gloamere-knowledge-capture",
    "gloamere-product-decision",
  ]) {
    assert.match(workflows, new RegExp(skill));
  }
  assert.match(workflows, /pinned MIT UI data and helper core/i);
  assert.match(workflows, /Official-directory GA remains gated/i);
  assert.match(workflows, /LAB ≠ RELEASE/);
});

test("policy routes preserve the public repository statements", async () => {
  const [privacy, terms, security, support] = await Promise.all([
    render("/privacy").then((response) => response.text()),
    render("/terms").then((response) => response.text()),
    render("/security").then((response) => response.text()),
    render("/support").then((response) => response.text()),
  ]);

  assert.match(privacy, /do not operate a Gloamere backend/i);
  assert.match(privacy, /do not.*collect telemetry/is);
  assert.match(terms, /MIT License/);
  assert.match(terms, /provided “as is,”/);
  assert.match(security, /private vulnerability reporting/);
  assert.match(security, /does not promise a fixed response-time SLA/);
  assert.match(support, /local Codex CLI execution only/);
  assert.match(support, /unobservable.*not automatically a routing failure/is);
});

test("removes the starter surface and keeps scripts cross-platform", async () => {
  const [packageText, layout, page, css] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);
  const packageJson = JSON.parse(packageText);

  assert.equal(packageJson.name, "gloamere-codex-plugins-site");
  assert.equal(packageJson.dependencies["react-loading-skeleton"], undefined);
  assert.equal(packageJson.scripts.dev, "vinext dev");
  assert.equal(packageJson.scripts.build, "vinext build");
  assert.equal(packageJson.scripts["build:static"], "node scripts/build-static.mjs");
  assert.equal(packageJson.scripts.start, "vinext start");
  assert.doesNotMatch(layout, /next\/font|Starter Project|favicon\.svg/);
  assert.doesNotMatch(page, /codex-preview|SkeletonPreview/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /ui-monospace/);
  assert.doesNotMatch(css, /backdrop-filter:\s*blur/);
  assert.match(css, /--archive:\s*#e8dcc5/i);
  assert.match(css, /border:\s*3px double var\(--rule-dark\)/);

  const [i18n, locale] = await Promise.all([
    readFile(new URL("../app/i18n.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/locale.ts", import.meta.url), "utf8"),
  ]);
  assert.match(i18n, /gloamere-locale/);
  assert.match(i18n, /navigator\.language/);
  assert.match(i18n, /aria-pressed/);
  assert.match(locale, /"zh-CN"/);

  await assert.rejects(
    access(new URL("../app/_sites-preview/SkeletonPreview.tsx", import.meta.url)),
  );
  await Promise.all([
    access(new URL("../public/gloamere-icon.png", import.meta.url)),
    access(new URL("../public/gloamere-logo.png", import.meta.url)),
    access(new URL("../public/og.png", import.meta.url)),
    access(new URL("../public/og-ios.png", import.meta.url)),
    access(new URL("../public/robots.txt", import.meta.url)),
    access(new URL("../public/sitemap.xml", import.meta.url)),
  ]);
  await assert.rejects(
    access(new URL("public/favicon.svg", templateRoot)),
  );
});
