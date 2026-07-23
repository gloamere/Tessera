import type { Metadata } from "next";
import {
  LegalPage,
  SECURITY_REPORT_URL,
} from "../site";

export const metadata: Metadata = {
  title: "Security",
  description:
    "Supported versions, private vulnerability reporting, and security boundaries for Gloamere.",
};

export default function SecurityPage() {
  return (
    <LegalPage
      route="Policy / Security"
      title="Verify the release. Report vulnerabilities privately."
      lead="Before the beta tag exists, reports target the release candidate; afterward, fixes target the latest published Gloamere 4.x tag."
    >
      <section>
        <h2>Supported versions</h2>
        <p>
          Historical 3.x artifacts are retained for traceability, but they are
          not an active compatibility or security-support surface.
        </p>
      </section>
      <section>
        <h2>Report a vulnerability</h2>
        <p>
          Use{" "}
          <a href={SECURITY_REPORT_URL}>
            GitHub private vulnerability reporting
          </a>
          . Do not open a public issue for a suspected vulnerability.
        </p>
        <p>
          Include the affected plugin and version, Codex, Python, and operating
          system versions, impact, reproduction steps, and a minimal proof of
          concept. Remove API keys, tokens, private prompts, personal paths, and
          customer data.
        </p>
        <p>
          Gloamere will acknowledge the report through GitHub and coordinate
          disclosure after a fix is available. The beta does not promise a
          fixed response-time SLA.
        </p>
      </section>
      <section>
        <h2>Security boundary</h2>
        <ul>
          <li>
            The prepared plugins contain no Gloamere backend, telemetry, hooks,
            MCP servers, or background services.
          </li>
          <li>
            Plugins still operate within the permissions and tools granted to
            Codex; users should review requested actions and protect local
            inputs.
          </li>
          <li>
            Install immutable tagged releases and compare archives against their
            published SHA-256 sidecars.
          </li>
          <li>
            Missing, malformed, truncated, or unknown Eval evidence is
            non-verified. A model statement is not proof that a Skill was
            loaded.
          </li>
        </ul>
      </section>
    </LegalPage>
  );
}
