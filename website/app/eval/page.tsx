import type { Metadata } from "next";
import {
  EvidenceTrace,
  HeroActions,
  InstallPanel,
  PageHero,
  SiteFrame,
} from "../site";

export const metadata: Metadata = {
  title: "Gloamere Eval",
  description:
    "Inspect, lint, and evaluate native Codex Skill activation while separating evidence coverage from conditional accuracy.",
};

const evidenceStates = [
  {
    state: "verified",
    meaning:
      "The recognized Codex event stream is complete, agrees with the model statement, and resolves to the locked Skill path.",
    verdict: "pass or fail",
  },
  {
    state: "unobservable",
    meaning:
      "The event stream is malformed, truncated, or contains an unknown event.",
    verdict: "null",
  },
  {
    state: "unavailable",
    meaning:
      "Codex, the plugin directory, or an enabled target cannot currently be observed.",
    verdict: "null",
  },
  {
    state: "identity_conflict",
    meaning:
      "The model statement, duplicate Skill name, installed identity, or target lock disagree.",
    verdict: "null",
  },
  {
    state: "execution_error",
    meaning: "Codex or the event adapter did not complete successfully.",
    verdict: "null",
  },
];

export default function EvalPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route="Plugin route / Eval"
            title="Measure what Codex actually loaded."
            summary="Gloamere Eval binds the plugin manifest, Skill, and agent configuration to exact paths and SHAs before observing native Codex activation. Evidence gaps stay visible instead of becoming false accuracy."
            aside={<EvidenceTrace compact />}
          >
            <HeroActions
              primaryHref="#install"
              primaryLabel="Install Gloamere Eval"
            />
          </PageHero>

          <section className="method-section">
            <div className="section-heading">
              <p className="eyebrow">Three explicit actions</p>
              <h2>Lock, validate, observe.</h2>
              <p>
                The runner uses Python 3.10+ standard library code and local
                Codex CLI execution. Each action has a separate responsibility.
              </p>
            </div>
            <ol className="method-list">
              <li>
                <span className="method-command">inspect</span>
                <div>
                  <h3>Lock the installed identity.</h3>
                  <p>
                    Record plugin ID and version, installed and enabled state,
                    plus path-bound SHA-256 values for the manifest, Skill, and
                    agent configuration.
                  </p>
                </div>
              </li>
              <li>
                <span className="method-command">lint</span>
                <div>
                  <h3>Reject drift before execution.</h3>
                  <p>
                    Validate the suite, target lock, or report, then reread the
                    target to catch content or identity changes.
                  </p>
                </div>
              </li>
              <li>
                <span className="method-command">native</span>
                <div>
                  <h3>Observe Codex’s event stream.</h3>
                  <p>
                    Run normal activation through <code>codex exec --json</code>{" "}
                    and verify the actual <code>SKILL.md</code> path. Unknown or
                    incomplete events fail closed.
                  </p>
                </div>
              </li>
            </ol>
          </section>

          <section className="evidence-section" id="evidence-status">
            <div className="section-heading">
              <p className="eyebrow">Evidence contract</p>
              <h2>Coverage and accuracy stay separate.</h2>
              <p>
                Only <code>verified</code> observations receive a routing
                verdict. Every other state explains why scoring is unavailable
                and returns <code>verdict = null</code>.
              </p>
            </div>
            <div className="evidence-table-wrap">
              <table className="evidence-table">
                <thead>
                  <tr>
                    <th scope="col">evidence_status</th>
                    <th scope="col">What it means</th>
                    <th scope="col">verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {evidenceStates.map((item) => (
                    <tr key={item.state}>
                      <th scope="row">
                        <code>{item.state}</code>
                      </th>
                      <td>{item.meaning}</td>
                      <td>
                        <code>{item.verdict}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="not-result-note">
              <strong>No admission claim.</strong>
              <p>
                This page describes the public evaluation contract. It does not
                claim that Gloamere has passed an official native-admission or
                directory review.
              </p>
            </aside>
          </section>

          <section className="privacy-by-default">
            <div>
              <p className="eyebrow">Report privacy</p>
              <h2>Hash the prompt. Keep the path local.</h2>
            </div>
            <ul>
              <li>
                Reports store the prompt SHA-256 by default, not the raw prompt.
              </li>
              <li>
                Raw prompts require an explicit <code>--include-prompts</code>{" "}
                choice after reviewing the privacy boundary.
              </li>
              <li>
                Reports do not copy absolute paths from the target lock.
              </li>
              <li>
                JSON goes to stdout unless the user supplies{" "}
                <code>--output</code>.
              </li>
            </ul>
          </section>

          <section className="scope-grid">
            <article>
              <p className="eyebrow">Designed to do</p>
              <h2>Inspect routing evidence.</h2>
              <ul className="check-list">
                <li>Evaluate native Codex Skill activation.</li>
                <li>Surface duplicate names and identity drift.</li>
                <li>Produce reproducible schema v3 reports.</li>
                <li>Read compatible historical schema v2 reports.</li>
              </ul>
            </article>
            <article>
              <p className="eyebrow">Designed not to do</p>
              <h2>Change the system under test.</h2>
              <ul className="cross-list">
                <li>Does not execute the task written inside a test case.</li>
                <li>Does not edit Skills or install dependencies.</li>
                <li>Does not treat model self-report as loading evidence.</li>
                <li>Does not bundle a business-specific benchmark suite.</li>
              </ul>
            </article>
          </section>
        </div>
        <InstallPanel plugin="eval" />
      </main>
    </SiteFrame>
  );
}
