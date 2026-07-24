import type { Metadata } from "next";
import Link from "next/link";
import { T } from "./i18n";
import { l } from "./locale";
import { REPOSITORY_URL, SiteFrame } from "./site";

export const metadata: Metadata = {
  title: "Evidence-led Codex tools",
  description:
    "Know what Codex actually loaded with evidence-led evaluation and focused professional workflows.",
  alternates: { canonical: "/" },
};

const evidenceSteps = [
  {
    index: "01",
    label: l("Prompt fingerprint", "提示词指纹"),
    field: "prompt_sha256",
    value: "96f3…d221",
  },
  {
    index: "02",
    label: l("Target identity", "目标身份"),
    field: "target_lock",
    value: "path + SHA-256",
  },
  {
    index: "03",
    label: l("Native observation", "原生观察"),
    field: "evidence_status",
    value: "verified / pass",
  },
];

export default function Home() {
  return (
    <SiteFrame showFooter={false}>
      <main id="main-content" className="home-main">
        <section className="commercial-showcase" aria-labelledby="home-title">
          <div className="showcase-copy">
            <div className="showcase-edition">
              <span>Gloamere / 4.0 Beta</span>
              <span>Codex only</span>
            </div>

            <div className="showcase-message">
              <p className="route-label">
                <T value={l("Evidence-led tools for Codex", "为 Codex 构建的证据驱动工具")} />
              </p>
              <h1 id="home-title">
                <T value={l("Know what ", "知道")} />
                <em><T value={l("Codex actually loaded.", "Codex 实际加载了什么。")} /></em>
              </h1>
              <p className="showcase-lead">
                <T value={l(
                  "Evaluate native Skill activation with observable evidence, then add focused workflows that load only when the task fits.",
                  "用可观察证据评测原生 Skill 调用，再加入只在任务匹配时加载的专注工作流。",
                )} />
              </p>
            </div>

            <div className="showcase-actions">
              <Link className="button button-primary" href="/eval">
                <T value={l("Explore Eval", "了解 Eval")} />
              </Link>
              <Link className="button button-secondary" href="/workflows">
                <T value={l("Explore Workflows", "了解 Workflows")} />
              </Link>
            </div>

            <dl className="showcase-facts">
              <div><dt><T value={l("Distribution", "发行版")} /></dt><dd>4.0.0-beta.1</dd></div>
              <div><dt><T value={l("Runtime", "运行环境")} /></dt><dd>Codex only</dd></div>
              <div><dt><T value={l("License", "许可证")} /></dt><dd>MIT</dd></div>
            </dl>
          </div>

          <aside className="showcase-evidence" aria-label="Illustrative evidence chain">
            <header className="showcase-evidence-header">
              <div>
                <span><T value={l("Native evidence", "原生证据")} /></span>
                <strong><T value={l("Observable by design", "为可观察而设计")} /></strong>
              </div>
              <span className="commercial-status">
                <i aria-hidden="true" />
                schema v3
              </span>
            </header>

            <ol className="commercial-trace">
              {evidenceSteps.map((step) => (
                <li key={step.index}>
                  <span className="commercial-trace-index">{step.index}</span>
                  <div>
                    <p><T value={step.label} /></p>
                    <code>{step.field}</code>
                  </div>
                  <strong>{step.value}</strong>
                </li>
              ))}
            </ol>

            <p className="commercial-boundary">
              <span><T value={l("Evidence rule", "证据规则")} /></span>
              <strong>verified → pass | fail</strong>
              <small><T value={l("Otherwise: verdict = null", "否则：verdict = null")} /></small>
            </p>

            <nav className="showcase-product-menu" aria-label="Product pages">
              <Link href="/eval">
                <span>01</span>
                <div>
                  <strong>Gloamere Eval</strong>
                  <small><T value={l("Inspect native Skill activation", "检查原生 Skill 调用")} /></small>
                </div>
                <b aria-hidden="true">↗</b>
              </Link>
              <Link href="/workflows">
                <span>02</span>
                <div>
                  <strong>Gloamere Workflows</strong>
                  <small><T value={l("Add four focused professional routes", "加入四条专注专业路径")} /></small>
                </div>
                <b aria-hidden="true">↗</b>
              </Link>
            </nav>

            <footer className="showcase-evidence-footer">
              <span><T value={l("Local by design", "本地运行")} /></span>
              <span><T value={l("No Gloamere telemetry", "不含 Gloamere 遥测")} /></span>
              <a href={REPOSITORY_URL}>GitHub ↗</a>
            </footer>
          </aside>
        </section>
      </main>
    </SiteFrame>
  );
}
