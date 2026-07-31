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
  ["/", /Evidence-backed product workflows/],
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
    if (pathname === "/") {
      assert.match(html, /href="\/workflows"/, pathname);
      assert.match(html, /href="\/support"/, pathname);
      assert.doesNotMatch(html, /href="\/eval"/, pathname);
    }
    assert.match(html, /href="\/privacy"/, pathname);
    assert.match(html, /href="\/terms"/, pathname);
    assert.match(html, /href="\/security"/, pathname);
    assert.match(html, /class="site-footer"/, pathname);
    assert.doesNotMatch(html, /property="og:image"/i);
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

test("home and plugin routes state the Git marketplace and product boundaries", async () => {
  const [home, evalPage, workflows] = await Promise.all([
    render("/").then((response) => response.text()),
    render("/eval").then((response) => response.text()),
    render("/workflows").then((response) => response.text()),
  ]);

  assert.match(home, /Turn evidence into.*the next clear move/is);
  assert.match(home, /Product Decision/);
  assert.match(home, /Visual Review/);
  assert.match(home, /Knowledge Capture/);
  assert.match(home, /Git marketplace release candidate/);
  assert.match(home, /Remote install after tag publication/);
  assert.match(home, /No Gloamere telemetry/);
  assert.doesNotMatch(home, /codex plugin marketplace add/);
  assert.doesNotMatch(home, /Gloamere Eval/);
  assert.equal(home.match(/<section\b/g)?.length, 1);

  assert.match(evalPage, /unobservable/);
  assert.match(evalPage, /identity_conflict/);
  assert.match(evalPage, /verdict = null/);
  assert.match(evalPage, /does not claim.*official native-admission/is);
  assert.match(evalPage, /Eval remains maintainer-only/i);
  assert.doesNotMatch(evalPage, /codex plugin (?:marketplace )?add/);
  assert.match(evalPage, /\.\/install\.ps1 -Source \. -Profile maintainer/);
  assert.match(evalPage, /sh install\.sh --source \. --profile maintainer/);
  assert.match(workflows, /Git marketplace release candidate/i);
  assert.doesNotMatch(workflows, /codex plugin (?:marketplace )?add/);
  assert.match(workflows, /\.\/install\.ps1 -Source \./);
  assert.match(workflows, /sh install\.sh --source \./);
  assert.match(workflows, /remote commands will appear.*only after.*tag/is);

  for (const skill of [
    "gloamere-product-decision",
    "gloamere-visual-review",
    "gloamere-knowledge-capture",
  ]) {
    assert.match(workflows, new RegExp(skill));
  }
  assert.ok(
    workflows.indexOf("gloamere-product-decision")
      < workflows.indexOf("gloamere-visual-review"),
  );
  assert.ok(
    workflows.indexOf("gloamere-visual-review")
      < workflows.indexOf("gloamere-knowledge-capture"),
  );
  assert.doesNotMatch(workflows, /gloamere-ui-system|vendor core/i);
  assert.match(workflows, /ChatGPT desktop.*Codex CLI/is);
  assert.match(workflows, /desktop release-candidate smoke test/i);
  assert.match(workflows, /no self-hosted web claim/i);
  assert.match(workflows, /no plugin UI, screenshots, MCP server/i);
  assert.match(workflows, /LAB ≠ RELEASE/);
});

test("policy routes preserve the public repository statements", async () => {
  const [privacy, terms, security, support] = await Promise.all([
    render("/privacy").then((response) => response.text()),
    render("/terms").then((response) => response.text()),
    render("/security").then((response) => response.text()),
    render("/support").then((response) => response.text()),
  ]);

  assert.match(privacy, /does not operate a Gloamere backend/i);
  assert.match(privacy, /does not.*collect Gloamere telemetry/is);
  assert.match(terms, /MIT License/);
  assert.match(terms, /provided “as is,”/);
  assert.match(security, /private vulnerability reporting/);
  assert.match(security, /does not promise a fixed response-time SLA/);
  assert.match(support, /ChatGPT desktop.*Codex CLI/is);
  assert.match(support, /desktop compatibility still requires.*smoke test/is);
  assert.match(support, /does not claim self-hosted installation.*ChatGPT Work web/is);
  assert.match(support, /remote installation is not live/i);
  assert.doesNotMatch(support, /support covers/i);
});

test("removes the starter surface and keeps scripts cross-platform", async () => {
  const [packageText, layout, page, css, site, workflows, generatedRelease] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/site.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/workflows/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/generated-release.ts", import.meta.url), "utf8"),
  ]);
  const packageJson = JSON.parse(packageText);

  assert.equal(packageJson.name, "gloamere-codex-plugins-site");
  assert.equal(packageJson.dependencies["react-loading-skeleton"], undefined);
  assert.equal(packageJson.scripts.dev, "vinext dev");
  assert.equal(packageJson.scripts.build, "vinext build");
  assert.equal(packageJson.scripts["build:static"], "node scripts/build-static.mjs");
  assert.equal(packageJson.scripts.start, "vinext start");
  assert.equal(packageJson.devDependencies["eslint-config-next"], undefined);
  assert.equal(packageJson.devDependencies.eslint, "10.8.0");
  assert.equal(packageJson.devDependencies["react-server-dom-webpack"], "19.2.8");
  assert.equal(packageJson.overrides.postcss, "8.5.25");
  assert.equal(packageJson.overrides["brace-expansion"], "5.0.9");
  assert.ok(packageJson.dependencies["@fontsource/playfair-display"]);
  assert.ok(packageJson.dependencies["@fontsource/ibm-plex-sans-condensed"]);
  assert.ok(packageJson.dependencies["@fontsource/ibm-plex-mono"]);
  assert.doesNotMatch(layout, /next\/font|Starter Project|favicon\.svg/);
  assert.doesNotMatch(page, /codex-preview|SkeletonPreview/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /ui-monospace/);
  assert.match(css, /"Playfair Display"/);
  assert.match(css, /"IBM Plex Sans Condensed"/);
  assert.match(css, /\.flow-main/);
  assert.doesNotMatch(css, /body:has\(\.home-main\)/);
  assert.match(css, /\.home-main[\s\S]*?min-height:\s*calc\(100svh - 5\.9rem\)/);
  assert.doesNotMatch(css, /--shell-width/);
  assert.match(css, /\.header-inner[\s\S]*?width:\s*100%/);
  assert.match(css, /\.commercial-showcase[\s\S]*?width:\s*calc\(100% - \(2 \* var\(--shell-pad\)\)\)[\s\S]*?min-height:\s*calc\(100svh - 5\.9rem\)[\s\S]*?padding-block:\s*clamp/);
  assert.doesNotMatch(css, /backdrop-filter:\s*blur/);
  assert.match(css, /--archive:\s*#e8dcc5/i);
  assert.match(css, /border:\s*3px double var\(--rule-dark\)/);
  assert.match(page, /releaseData/);
  const releaseState = await readFile(
    new URL("../app/release-state.ts", import.meta.url),
    "utf8",
  );
  assert.match(releaseState, /releaseData\.releaseStatus/);
  assert.match(releaseState, /RELEASE_PUBLISHED/);
  assert.match(site, /MARKETPLACE_ADD_COMMAND/);
  assert.match(site, /RELEASE_PUBLISHED/);
  assert.doesNotMatch(site, /hasApprovedDirectoryListing/);
  assert.match(workflows, /releaseSkillIds/);
  assert.match(generatedRelease, /Generated by scripts\/generate_release_files\.py/);

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

  const sitemap = await readFile(new URL("../public/sitemap.xml", import.meta.url), "utf8");
  assert.doesNotMatch(sitemap, /\/eval<\/loc>/);
});
