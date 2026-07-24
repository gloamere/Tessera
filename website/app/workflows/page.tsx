import type { Metadata } from "next";
import {
  BetaBoundary,
  HeroActions,
  InstallPanel,
  PageHero,
  REPOSITORY_URL,
  SiteFrame,
} from "../site";

export const metadata: Metadata = {
  title: "Gloamere Workflows",
  description:
    "Four focused Codex Skills for UI systems, visual review, durable knowledge, and product decisions.",
  alternates: {
    canonical: "/workflows",
  },
};

const skills = [
  {
    id: "gloamere-ui-system",
    title: "UI System",
    trigger:
      "New UI, systematic redesign, design tokens, responsive behavior, or implementation constraints.",
    output:
      "A coherent direction, token system, layout and state rules, accessibility boundaries, and stack-aware implementation guidance.",
    boundary:
      "Not for backend-only work, isolated functional bugs, copy editing, user research, or conversion experiments.",
    status: "Stable Skill identity · Beta vendor core",
  },
  {
    id: "gloamere-visual-review",
    title: "Visual Review",
    trigger:
      "An existing interface, screenshot, design draft, component, or visual artifact needs an evidence-led review.",
    output:
      "Visible observations, their user impact, up to three prioritized changes, and a concrete validation method.",
    boundary:
      "Not for creating a system from zero, text-only polish, or design advice without an inspectable artifact.",
    status: "Stable Skill identity · Gloamere-authored",
  },
  {
    id: "gloamere-knowledge-capture",
    title: "Knowledge Capture",
    trigger:
      "A conversation, research set, operating lesson, or project decision should become maintainable Markdown knowledge.",
    output:
      "De-duplicated, linked records that preserve sources, status, dates, ownership, and open questions.",
    boundary:
      "Not for transient chat summaries, generic prose editing, or a one-off answer with no target knowledge base.",
    status: "Stable Skill identity · Gloamere-authored",
  },
  {
    id: "gloamere-product-decision",
    title: "Product Decision",
    trigger:
      "Existing research, data, and constraints need to converge into a scoped product choice.",
    output:
      "A recommendation, evidence ledger, alternatives, tradeoffs, success measures, risks, open questions, and the next validation.",
    boundary:
      "Not for pretending research occurred, growth execution, internal operations, or implementation planning after the choice is made.",
    status: "Stable Skill identity · Gloamere-authored",
  },
];

export default function WorkflowsPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route="Plugin route / Workflows"
            title="Four workflows. Loaded only when the task fits."
            summary="Gloamere Workflows adds four stable Skill identities with explicit trigger and exclusion boundaries. The bundle is installed once; Codex still decides which matching Skill to load."
            aside={
              <div className="workflow-orbit" aria-label="Four workflow Skills">
                <div className="orbit-core">task</div>
                <span className="orbit-item orbit-ui">UI system</span>
                <span className="orbit-item orbit-review">visual review</span>
                <span className="orbit-item orbit-knowledge">knowledge</span>
                <span className="orbit-item orbit-decision">decision</span>
              </div>
            }
          >
            <HeroActions
              primaryHref="#install"
              primaryLabel="Install Gloamere Workflows"
            />
          </PageHero>

          <section className="skill-section">
            <div className="section-heading">
              <p className="eyebrow">Stable Skill surface</p>
              <h2>Each route earns its turn.</h2>
              <p>
                Installation does not preload all four workflows. Codex uses
                their descriptions and the user’s request to discover the
                relevant route.
              </p>
            </div>
            <div className="skill-index">
              {skills.map((skill) => (
                <article key={skill.id} className="skill-entry">
                  <header>
                    <p className="plugin-id">{skill.id}</p>
                    <h3>{skill.title}</h3>
                    <span className="skill-status">{skill.status}</span>
                  </header>
                  <dl>
                    <div>
                      <dt>Use when</dt>
                      <dd>{skill.trigger}</dd>
                    </div>
                    <div>
                      <dt>Produces</dt>
                      <dd>{skill.output}</dd>
                    </div>
                    <div>
                      <dt>Boundary</dt>
                      <dd>{skill.boundary}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          <section className="provenance-section">
            <div className="provenance-title">
              <p className="eyebrow">Provenance is part of the product</p>
              <h2>Original workflow contracts. One isolated vendor core.</h2>
            </div>
            <div className="provenance-ledger">
              <article>
                <span className="ledger-mark ledger-original">original</span>
                <h3>Three Gloamere-authored Skills</h3>
                <p>
                  Visual Review, Knowledge Capture, and Product Decision were
                  rewritten around Gloamere boundaries, failure categories, and
                  output contracts. Their current hashes are recorded in the
                  repository audit.
                </p>
              </article>
              <article>
                <span className="ledger-mark ledger-vendor">isolated</span>
                <h3>UI System vendor core</h3>
                <p>
                  The GitHub beta candidate contains a pinned MIT UI data and
                  helper core. Its exact file boundary, upstream commit,
                  adjustment, and complete license notice are preserved.
                </p>
              </article>
              <article>
                <span className="ledger-mark ledger-gate">GA gate</span>
                <h3>Original replacement required</h3>
                <p>
                  Official-directory GA remains gated on replacing that vendor
                  core with Gloamere-owned taxonomy, data, scripts, and rules,
                  then rerunning identity, routing, and quality evaluations.
                </p>
              </article>
            </div>
            <a
              className="text-link"
              href={`${REPOSITORY_URL}/blob/main/plugins/gloamere-workflows/PROVENANCE.md`}
            >
              Read the full provenance record
            </a>
          </section>

          <BetaBoundary />

          <section className="experiment-note">
            <span>LAB ≠ RELEASE</span>
            <div>
              <h2>Experiments stay outside the plugin.</h2>
              <p>
                Repository labs may explore future workflows, but they are not
                bundled, supported, or presented as release Skills. Finance,
                growth, and general business-operations Skills are also outside
                the 4.0 beta candidate.
              </p>
            </div>
          </section>
        </div>
        <InstallPanel plugin="workflows" />
      </main>
    </SiteFrame>
  );
}
