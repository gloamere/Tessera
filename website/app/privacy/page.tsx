import type { Metadata } from "next";
import { ISSUE_TRACKER_URL, LegalPage } from "../site";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "Privacy boundaries for Gloamere Eval and Gloamere Workflows.",
  alternates: {
    canonical: "/privacy",
  },
};

export default function PrivacyPage() {
  return (
    <LegalPage
      route="Policy / Privacy"
      title="Local plugins. No Gloamere telemetry."
      lead="Last updated July 23, 2026."
    >
      <section>
        <h2>What Gloamere does not collect</h2>
        <p>
          Gloamere Eval and Gloamere Workflows are local, skill-based Codex
          plugins. They do not operate a Gloamere backend, create user accounts,
          set cookies, collect telemetry, or transmit analytics to Gloamere.
        </p>
      </section>
      <section>
        <h2>Local inputs and outputs</h2>
        <p>
          Gloamere Eval reads the case files and project context selected by the
          user. It writes JSON to stdout by default and creates a report file
          only when the user explicitly supplies <code>--output</code>.
        </p>
        <p>
          Gloamere Workflows use the project files and Codex capabilities
          authorized by the user. Bundled helper scripts operate locally.
        </p>
      </section>
      <section>
        <h2>Other services</h2>
        <p>
          Codex and any tools, connectors, websites, or services the user
          separately chooses to invoke are governed by their own privacy terms.
          Gloamere does not receive that data merely because one of these
          plugins is installed.
        </p>
      </section>
      <section>
        <h2>Questions</h2>
        <p>
          Raise privacy questions through the{" "}
          <a href={ISSUE_TRACKER_URL}>public issue tracker</a>. Do not include
          private prompts, credentials, personal paths, or customer data.
        </p>
      </section>
    </LegalPage>
  );
}
