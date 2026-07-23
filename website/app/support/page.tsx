import type { Metadata } from "next";
import Link from "next/link";
import {
  ISSUE_TRACKER_URL,
  PageHero,
  SiteFrame,
} from "../site";

export const metadata: Metadata = {
  title: "Support",
  description:
    "Support scope and reporting guidance for the Gloamere 4.0 beta candidate.",
};

export default function SupportPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route="Support / Beta candidate"
            title="Bring the smallest safe reproduction."
            summary="Before the beta tag is published, support covers release-candidate review. After publication it covers that exact Gloamere Eval and Workflows tag on Codex App, CLI, and IDE. Eval 4.0 supports local Codex CLI execution only."
            aside={
              <div className="support-signal">
                <span>report</span>
                <strong>reproduce</strong>
                <strong>redact</strong>
                <strong>identify</strong>
                <span>resolve</span>
              </div>
            }
          />

          <section className="support-grid">
            <article>
              <p className="eyebrow">Before opening a report</p>
              <h2>Make the environment observable.</h2>
              <ol className="support-checklist">
                <li>
                  Record the exact Gloamere tag, plugin version, Codex version,
                  operating system, and Python version when Eval is involved.
                </li>
                <li>Reproduce the issue in a new Codex task.</li>
                <li>
                  Run <code>codex plugin list --json</code> and confirm the
                  intended plugin is installed and enabled.
                </li>
                <li>
                  Remove secrets, prompt contents, usernames, and absolute local
                  paths from logs or reports.
                </li>
              </ol>
            </article>
            <aside className="support-actions">
              <div>
                <p className="eyebrow">Public issue</p>
                <h2>Bugs, docs, installation, features</h2>
                <p>
                  Include a minimal reproduction and the relevant{" "}
                  <code>evidence_status</code>. An <code>unobservable</code>{" "}
                  result is not automatically a routing failure.
                </p>
                <a className="button button-primary" href={ISSUE_TRACKER_URL}>
                  Open the issue tracker
                </a>
              </div>
              <div>
                <p className="eyebrow">Security issue</p>
                <h2>Report privately</h2>
                <p>
                  Suspected vulnerabilities must not be posted to the public
                  issue tracker.
                </p>
                <Link className="button button-secondary" href="/security">
                  Read security reporting
                </Link>
              </div>
            </aside>
          </section>

          <section className="support-boundary">
            <p className="eyebrow">Outside support scope</p>
            <h2>Keep experiments and old identities separate.</h2>
            <p>
              Gloamere does not provide support for unpublished experimental
              workflows, modified forks, old plugin identities, or
              compatibility with non-Codex hosts.
            </p>
          </section>
        </div>
      </main>
    </SiteFrame>
  );
}
