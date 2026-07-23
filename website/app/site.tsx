import Link from "next/link";
import Image from "next/image";
import type { ReactNode } from "react";

export const REPOSITORY_URL =
  "https://github.com/gloamere/codex-plugins";
export const ISSUE_TRACKER_URL = `${REPOSITORY_URL}/issues`;
export const SECURITY_REPORT_URL = `${REPOSITORY_URL}/security/advisories/new`;
export const RELEASE_TAG = "v4.0.0-beta.1";

const navigation = [
  { href: "/eval", label: "Eval" },
  { href: "/workflows", label: "Workflows" },
  { href: "/support", label: "Support" },
];

export function SiteFrame({ children }: { children: ReactNode }) {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <SiteHeader />
      {children}
      <SiteFooter />
    </>
  );
}

function SiteHeader() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand-link" href="/" aria-label="Gloamere home">
          <Image
            className="brand-icon"
            src="/gloamere-icon.png"
            width="34"
            height="34"
            alt=""
            unoptimized
          />
          <span>Gloamere</span>
        </Link>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="header-actions">
          <span className="beta-mark">4.0 Beta candidate</span>
          <a href={REPOSITORY_URL}>GitHub</a>
        </div>
      </div>
    </header>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <Image
            src="/gloamere-icon.png"
            width="28"
            height="28"
            alt=""
            unoptimized
          />
          <div>
            <strong>Gloamere</strong>
            <p>Evidence-led plugins for Codex.</p>
          </div>
        </div>
        <nav className="footer-nav" aria-label="Footer navigation">
          <Link href="/support">Support</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/security">Security</Link>
          <a href={REPOSITORY_URL}>Source</a>
        </nav>
        <p className="footer-note">
          MIT licensed. Beta candidate. No Gloamere backend or telemetry.
        </p>
      </div>
    </footer>
  );
}

type PageHeroProps = {
  route: string;
  title: string;
  summary: string;
  aside?: ReactNode;
  children?: ReactNode;
};

export function PageHero({
  route,
  title,
  summary,
  aside,
  children,
}: PageHeroProps) {
  return (
    <section className="page-hero">
      <div className="page-hero-copy">
        <p className="route-label">{route}</p>
        <h1>{title}</h1>
        <p className="hero-summary">{summary}</p>
        {children}
      </div>
      {aside ? <div className="page-hero-aside">{aside}</div> : null}
    </section>
  );
}

export function HeroActions({
  primaryHref,
  primaryLabel,
}: {
  primaryHref: string;
  primaryLabel: string;
}) {
  return (
    <div className="hero-actions">
      <Link className="button button-primary" href={primaryHref}>
        {primaryLabel}
      </Link>
      <a className="button button-secondary" href={REPOSITORY_URL}>
        Browse source
      </a>
    </div>
  );
}

export function EvidenceTrace({ compact = false }: { compact?: boolean }) {
  return (
    <figure className={`evidence-trace${compact ? " evidence-trace-compact" : ""}`}>
      <figcaption className="trace-heading">
        <span>Report field anatomy</span>
        <span className="schema-chip">schema v3</span>
      </figcaption>
      <ol className="trace-list">
        <li className="trace-node">
          <span className="trace-step">prompt</span>
          <code>prompt_sha256</code>
          <strong>96f3…d221</strong>
          <small>Raw prompt omitted by default</small>
        </li>
        <li className="trace-node">
          <span className="trace-step">target lock</span>
          <code>plugin / path / SHA</code>
          <strong>gloamere-workflows</strong>
          <small>SKILL.md · 11b8…8409</small>
        </li>
        <li className="trace-node trace-node-result">
          <span className="trace-step">observation</span>
          <code>evidence_status</code>
          <strong>verified</strong>
          <small>
            verdict <b>pass</b>
          </small>
        </li>
      </ol>
      <p className="trace-disclaimer">
        Illustrative field anatomy—not a published native-admission result.
      </p>
    </figure>
  );
}

export function InstallPanel({
  plugin = "both",
}: {
  plugin?: "eval" | "workflows" | "both";
}) {
  const pluginCommands =
    plugin === "eval"
      ? ["codex plugin add gloamere-eval@gloamere"]
      : plugin === "workflows"
        ? ["codex plugin add gloamere-workflows@gloamere"]
        : [
            "codex plugin add gloamere-eval@gloamere",
            "codex plugin add gloamere-workflows@gloamere",
          ];

  return (
    <section className="install-section" id="install">
      <div className="section-heading">
        <p className="eyebrow">Planned pinned installation</p>
        <h2>Install only after the immutable beta tag is published.</h2>
        <p>
          These commands become valid only after the release gate passes and
          the exact tag is published. Nothing will be fetched from a moving
          branch.
        </p>
      </div>
      <div className="install-console" aria-label="Installation commands">
        <div className="console-bar">
          <span>Codex CLI</span>
          <span>{RELEASE_TAG}</span>
        </div>
        <pre>
          <code>
            <span>
              codex plugin marketplace add gloamere/codex-plugins --ref{" "}
              {RELEASE_TAG}
            </span>
            {pluginCommands.map((command) => (
              <span key={command}>{command}</span>
            ))}
            <span>codex plugin list --json</span>
          </code>
        </pre>
      </div>
      <div className="install-notes">
        <p>
          <strong>Default installer:</strong> installs Gloamere Eval.
        </p>
        <p>
          <strong>Legacy safety:</strong> detects old <code>@tessera</code>{" "}
          selectors but never removes, disables, or modifies them.
        </p>
        <a href={`${REPOSITORY_URL}#install-the-pinned-beta`}>
          PowerShell, macOS, and Linux installer commands
        </a>
      </div>
    </section>
  );
}

export function BetaBoundary() {
  return (
    <aside className="boundary-panel" aria-labelledby="beta-boundary-title">
      <div>
        <p className="eyebrow">Release boundary</p>
        <h2 id="beta-boundary-title">What the 4.0 Beta candidate contains.</h2>
      </div>
      <dl>
        <div>
          <dt>Prepared</dt>
          <dd>
            Two Codex-only plugins and four stable workflow Skill identities;
            the release tag remains gated on current native evidence.
          </dd>
        </div>
        <div>
          <dt>Isolated</dt>
          <dd>
            The UI System beta includes a pinned MIT vendor core with preserved
            notices and an explicit file boundary.
          </dd>
        </div>
        <div>
          <dt>Not shipped</dt>
          <dd>
            Repository experiments and finance, growth, or general
            business-operations Skills.
          </dd>
        </div>
        <div>
          <dt>GA gate</dt>
          <dd>
            Official-directory GA requires replacing the UI vendor core with
            Gloamere-owned taxonomy, data, scripts, and rules, then rerunning
            evaluations at the new SHA.
          </dd>
        </div>
      </dl>
    </aside>
  );
}

export function LegalPage({
  route,
  title,
  lead,
  children,
}: {
  route: string;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <SiteFrame>
      <main id="main-content" className="legal-layout">
        <header className="legal-header">
          <p className="route-label">{route}</p>
          <h1>{title}</h1>
          <p>{lead}</p>
        </header>
        <article className="legal-copy">{children}</article>
      </main>
    </SiteFrame>
  );
}
