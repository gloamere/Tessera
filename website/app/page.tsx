import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import {
  BetaBoundary,
  EvidenceTrace,
  HeroActions,
  InstallPanel,
  REPOSITORY_URL,
  SiteFrame,
} from "./site";

export const metadata: Metadata = {
  title: "Evidence-led Codex plugins",
  description:
    "Evaluate Codex Skill routing with observable evidence and add four focused professional workflows.",
  alternates: {
    canonical: "/",
  },
};

const workflowSkills = [
  "gloamere-ui-system",
  "gloamere-visual-review",
  "gloamere-knowledge-capture",
  "gloamere-product-decision",
];

export default function Home() {
  return (
    <SiteFrame>
      <main id="main-content">
        <section className="home-hero">
          <div className="home-hero-copy">
            <p className="route-label">
              Gloamere / Codex plugins / 4.0 Beta candidate
            </p>
            <h1>
              Codex workflows with a visible chain of{" "}
              <span>evidence.</span>
            </h1>
            <p className="hero-summary">
              Two self-contained plugins: inspect native Skill activation
              without guessing, then add four focused workflows that load only
              when the task fits.
            </p>
            <HeroActions
              primaryHref="#install"
              primaryLabel="Review the planned install"
            />
          </div>
          <EvidenceTrace />
        </section>

        <section className="release-line" aria-label="Release facts">
          <p>
            <span>Distribution</span>
            <strong>4.0.0-beta.1</strong>
          </p>
          <p>
            <span>Runtime</span>
            <strong>Codex only</strong>
          </p>
          <p>
            <span>Services</span>
            <strong>None added</strong>
          </p>
          <p>
            <span>License</span>
            <strong>MIT</strong>
          </p>
        </section>

        <section className="routes-section">
          <div className="section-heading">
            <p className="eyebrow">Two routes, one principle</p>
            <h2>Make the work inspectable.</h2>
            <p>
              Each plugin stays inside Codex’s native lifecycle. There is no
              second router, background process, telemetry layer, hook, or MCP
              server.
            </p>
          </div>
          <div className="plugin-routes">
            <article className="plugin-route plugin-route-eval">
              <div className="route-index">EVAL</div>
              <div className="route-content">
                <p className="plugin-id">gloamere-eval</p>
                <h3>Measure what Codex actually loaded.</h3>
                <p>
                  Lock the plugin manifest, Skill, and agent configuration to
                  exact paths and SHAs, observe native Codex events, and keep
                  missing evidence out of the accuracy score.
                </p>
                <ul className="inline-facts" aria-label="Eval capabilities">
                  <li>inspect</li>
                  <li>lint</li>
                  <li>native</li>
                  <li>schema v3</li>
                </ul>
                <Link className="text-link" href="/eval">
                  Explore Gloamere Eval
                </Link>
              </div>
            </article>
            <article className="plugin-route plugin-route-workflows">
              <div className="route-index">FLOW</div>
              <div className="route-content">
                <p className="plugin-id">gloamere-workflows</p>
                <h3>Load a focused workflow when its boundary matches.</h3>
                <p>
                  Four independently described Skills for UI systems, visual
                  review, durable knowledge, and product decisions. Installing
                  the bundle does not load all four on every turn.
                </p>
                <ul className="skill-ribbon" aria-label="Bundled workflow Skills">
                  {workflowSkills.map((skill) => (
                    <li key={skill}>{skill.replace("gloamere-", "")}</li>
                  ))}
                </ul>
                <Link className="text-link" href="/workflows">
                  Explore Gloamere Workflows
                </Link>
              </div>
            </article>
          </div>
        </section>

        <section className="proof-section">
          <div className="proof-statement">
            <p className="eyebrow">Evidence before verdict</p>
            <h2>“The model said so” is not proof.</h2>
          </div>
          <div className="proof-copy">
            <p>
              A verified Eval attempt needs a complete, recognized Codex event
              stream that agrees with the target lock. Truncated, malformed, or
              unknown evidence closes without a scored verdict.
            </p>
            <div className="status-equation" aria-label="Evidence rule">
              <code>verified</code>
              <span>→</span>
              <code>pass | fail</code>
              <b>otherwise</b>
              <code>verdict = null</code>
            </div>
            <Link className="text-link" href="/eval#evidence-status">
              Read the evidence contract
            </Link>
          </div>
        </section>

        <BetaBoundary />
        <InstallPanel />

        <section className="closing-section">
          <Image
            src="/gloamere-logo.png"
            width="160"
            height="160"
            alt=""
            unoptimized
          />
          <div>
            <p className="eyebrow">Open source, local by design</p>
            <h2>Review the exact release before Codex loads it.</h2>
            <p>
              The repository publishes deterministic plugin archives and
              SHA-256 sidecars. Gloamere adds no account, analytics endpoint, or
              hosted runtime.
            </p>
            <a className="button button-secondary" href={REPOSITORY_URL}>
              Inspect the repository
            </a>
          </div>
        </section>
      </main>
    </SiteFrame>
  );
}
