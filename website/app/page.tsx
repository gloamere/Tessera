import type { Metadata } from "next";
import Link from "next/link";
import { releaseData } from "./generated-release";
import { T } from "./i18n";
import { l } from "./locale";
import { DIRECTORY_APPROVED, DIRECTORY_STATUS } from "./release-state";
import {
  REPOSITORY_URL,
  SiteFrame,
} from "./site";

export const metadata: Metadata = {
  title: "Evidence-backed product workflows",
  description:
    "Turn evidence into product decisions, visual reviews, and durable knowledge with three focused workflows.",
  alternates: { canonical: "/" },
};

const workflowSteps = [
  {
    index: "01",
    label: l("Make the decision", "做出决策"),
    field: "product-decision",
    value: l("scope + evidence", "范围 + 证据"),
  },
  {
    index: "02",
    label: l("Review the artifact", "评审产物"),
    field: "visual-review",
    value: l("observe + prioritize", "观察 + 排序"),
  },
  {
    index: "03",
    label: l("Preserve the learning", "沉淀认知"),
    field: "knowledge-capture",
    value: l("source + link", "来源 + 互链"),
  },
];

const directoryPlugin = releaseData.plugins.find(
  (plugin) => plugin.publicRole === "directory",
);

if (!directoryPlugin) {
  throw new Error("Generated release data must include a directory plugin.");
}

export default function Home() {
  return (
    <SiteFrame>
      <main id="main-content" className="home-main">
        <section className="commercial-showcase" aria-labelledby="home-title">
          <div className="showcase-copy">
            <div className="showcase-edition">
              <span>{directoryPlugin.displayName} / {directoryPlugin.version}</span>
              <span><T value={DIRECTORY_STATUS} /></span>
            </div>

            <div className="showcase-message">
              <p className="route-label">
                <T value={l("For product and design leaders", "面向产品与设计负责人")} />
              </p>
              <h1 id="home-title">
                <T value={l("Turn evidence into ", "把证据转化为")} />
                <em><T value={l("the next clear move.", "清晰的下一步。")} /></em>
              </h1>
              <p className="showcase-lead">
                <T value={l(
                  "Three focused workflows help teams decide what to build, review what is visible, and preserve what they learned—without pretending missing evidence exists.",
                  "三个聚焦工作流帮助团队决定做什么、评审看得见的产物，并沉淀已经学到的内容——不会把缺失证据当成既有事实。",
                )} />
              </p>
            </div>

            <div className="showcase-actions">
              <Link className="button button-primary" href="/workflows">
                <T value={l("Explore the three workflows", "了解三个工作流")} />
              </Link>
              <Link className="button button-secondary" href="/support">
                <T value={l("Check directory status", "查看目录状态")} />
              </Link>
            </div>

            <dl className="showcase-facts">
              <div><dt><T value={l("Product", "产品")} /></dt><dd>{directoryPlugin.displayName}</dd></div>
              <div><dt><T value={l("Format", "形态")} /></dt><dd>Skills only</dd></div>
              <div><dt><T value={l("Languages", "语言")} /></dt><dd>中文 + English</dd></div>
            </dl>
          </div>

          <aside className="showcase-evidence" aria-label="Product workflow">
            <header className="showcase-evidence-header">
              <div>
                <span><T value={l("Product workflow", "产品工作流")} /></span>
                <strong><T value={l("Decide. Review. Preserve.", "决策、评审、沉淀。")} /></strong>
              </div>
              <span className="commercial-status">
                <i aria-hidden="true" />
                {directoryPlugin.skills.length} <T value={l("focused Skills", "个聚焦 Skill")} />
              </span>
            </header>

            <ol className="commercial-trace">
              {workflowSteps.map((step) => (
                <li key={step.index}>
                  <span className="commercial-trace-index">{step.index}</span>
                  <div>
                    <p><T value={step.label} /></p>
                    <code>{step.field}</code>
                  </div>
                  <strong><T value={step.value} /></strong>
                </li>
              ))}
            </ol>

            <p className="commercial-boundary">
              <span><T value={l("Directory status", "目录状态")} /></span>
              <strong><T value={DIRECTORY_STATUS} /></strong>
              <small>
                <T value={DIRECTORY_APPROVED
                  ? l("Use the verified listing", "通过已验证条目使用")
                  : l("Install after approval", "获批后开放安装")} />
              </small>
            </p>

            <nav className="showcase-product-menu" aria-label="Workflow Skills">
              <Link href="/workflows#product-decision">
                <span>01</span>
                <div>
                  <strong><T value={l("Product Decision", "产品决策")} /></strong>
                  <small><T value={l("Converge on a scoped choice", "收敛为边界明确的选择")} /></small>
                </div>
                <b aria-hidden="true">↗</b>
              </Link>
              <Link href="/workflows#visual-review">
                <span>02</span>
                <div>
                  <strong><T value={l("Visual Review", "视觉评审")} /></strong>
                  <small><T value={l("Prioritize visible improvements", "明确可见改进的优先级")} /></small>
                </div>
                <b aria-hidden="true">↗</b>
              </Link>
              <Link href="/workflows#knowledge-capture">
                <span>03</span>
                <div>
                  <strong><T value={l("Knowledge Capture", "知识沉淀")} /></strong>
                  <small><T value={l("Preserve sources and decisions", "保留来源与决策")} /></small>
                </div>
                <b aria-hidden="true">↗</b>
              </Link>
            </nav>

            <footer className="showcase-evidence-footer">
              <span><T value={l("Skills-only", "仅含 Skills")} /></span>
              <span><T value={l("No Gloamere telemetry", "不含 Gloamere 遥测")} /></span>
              <a href={REPOSITORY_URL}>GitHub ↗</a>
            </footer>
          </aside>
        </section>
      </main>
    </SiteFrame>
  );
}
