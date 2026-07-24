import type { Metadata } from "next";
import {
  ISSUE_TRACKER_URL,
  LegalPage,
  REPOSITORY_URL,
} from "../site";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms of use for Gloamere Codex plugins.",
  alternates: {
    canonical: "/terms",
  },
};

export default function TermsPage() {
  return (
    <LegalPage
      route="Policy / Terms"
      title="Open source, used with review."
      lead="Last updated July 23, 2026."
    >
      <section>
        <h2>License and warranty</h2>
        <p>
          Gloamere Eval and Gloamere Workflows are provided under the
          repository’s{" "}
          <a href={`${REPOSITORY_URL}/blob/main/LICENSE`}>MIT License</a>. They
          are provided “as is,” without warranties or a guarantee that generated
          analysis, recommendations, or reports are complete or correct.
        </p>
      </section>
      <section>
        <h2>User responsibility</h2>
        <p>
          Users remain responsible for reviewing plugin output, protecting
          confidential data, respecting third-party rights, and approving any
          action performed through Codex or another tool.
        </p>
      </section>
      <section>
        <h2>Professional advice</h2>
        <p>
          The workflows do not replace professional legal, financial, tax,
          security, medical, or compliance advice.
        </p>
      </section>
      <section>
        <h2>Acceptance and questions</h2>
        <p>
          By using a plugin, the user agrees to the license and these terms.
          Questions may be raised through the{" "}
          <a href={ISSUE_TRACKER_URL}>public issue tracker</a>.
        </p>
      </section>
    </LegalPage>
  );
}
