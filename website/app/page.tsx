import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { T } from "./i18n";
import { l } from "./locale";
import {
  BetaBoundary,
  EvidenceFlow,
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
  alternates: { canonical: "/" },
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
            <p className="route-label">Gloamere / Evidence archive / 4.0 Beta</p>
            <h1>
              <T value={l("Evidence-led ", "证据驱动的")} />
              <span><T value={l("Codex tools.", "Codex 工具。")} /></span>
            </h1>
            <p className="hero-summary">
              <strong className="hero-thesis">
                <T value={l("Know what Codex actually loaded.", "知道 Codex 实际加载了什么。")} />
              </strong>
              <T value={l(
                "Two self-contained plugins: inspect native Skill activation without guessing, then add four focused workflows that load only when the task fits.",
                "两个自包含插件：不靠猜测地检查原生 Skill 调用，再提供四个只在任务匹配时加载的专注工作流。",
              )} />
            </p>
            <HeroActions
              primaryHref="#install"
              primaryLabel={l("Review the pinned install", "查看固定版本安装")}
            />
          </div>
          <EvidenceTrace />
        </section>

        <section className="release-line glass" aria-label="Release facts">
          <p><span><T value={l("Distribution", "发行版")} /></span><strong>4.0.0-beta.1</strong></p>
          <p><span><T value={l("Runtime", "运行环境")} /></span><strong>Codex only</strong></p>
          <p><span><T value={l("Services", "新增服务")} /></span><strong><T value={l("None", "无")} /></strong></p>
          <p><span><T value={l("License", "许可证")} /></span><strong>MIT</strong></p>
        </section>

        <EvidenceFlow />

        <section className="routes-section">
          <div className="section-heading">
            <p className="eyebrow"><T value={l("Two routes, one principle", "两条路径，一个原则")} /></p>
            <h2><T value={l("Two dossiers. One standard of proof.", "两份档案，同一套证据标准。")} /></h2>
            <p><T value={l(
              "Each plugin stays inside Codex’s native lifecycle. There is no second router, background process, telemetry layer, hook, or MCP server.",
              "每个插件都留在 Codex 原生生命周期内，不引入第二套路由器、后台进程、遥测层、Hook 或 MCP 服务器。",
            )} /></p>
          </div>
          <div className="plugin-routes">
            <article className="plugin-route glass">
              <header className="route-record-header">
                <span>CASE / GM-EVAL-001</span>
                <strong><T value={l("Release candidate", "发布候选")} /></strong>
              </header>
              <div className="route-index">01</div>
              <div className="route-content">
                <p className="plugin-id">gloamere-eval</p>
                <h3><T value={l("Measure what Codex actually loaded.", "评测 Codex 实际加载了什么。")} /></h3>
                <p><T value={l(
                  "Lock the plugin manifest, Skill, and agent configuration to exact paths and SHAs, observe native Codex events, and keep missing evidence out of the accuracy score.",
                  "把插件清单、Skill 与 agent 配置绑定到精确路径和 SHA，观察原生 Codex 事件，并把缺失证据排除在准确率之外。",
                )} /></p>
                <ul className="inline-facts" aria-label="Eval capabilities">
                  <li>inspect</li><li>lint</li><li>native</li><li>schema v3</li>
                </ul>
                <dl className="route-metadata">
                  <div><dt><T value={l("Evidence", "证据")} /></dt><dd><T value={l("Codex native event stream", "Codex 原生事件流")} /></dd></div>
                  <div><dt><T value={l("Execution", "执行")} /></dt><dd><T value={l("Local Codex CLI", "本地 Codex CLI")} /></dd></div>
                </dl>
                <Link className="text-link" href="/eval">
                  <T value={l("Explore Gloamere Eval", "了解 Gloamere Eval")} />
                </Link>
              </div>
            </article>
            <article className="plugin-route glass">
              <header className="route-record-header">
                <span>CASE / GM-FLOW-001</span>
                <strong><T value={l("Four stable Skills", "四个稳定 Skill")} /></strong>
              </header>
              <div className="route-index">02</div>
              <div className="route-content">
                <p className="plugin-id">gloamere-workflows</p>
                <h3><T value={l("Load a focused workflow when its boundary matches.", "只在边界匹配时加载专注工作流。")} /></h3>
                <p><T value={l(
                  "Four independently described Skills for UI systems, visual review, durable knowledge, and product decisions. Installing the bundle does not load all four on every turn.",
                  "四个独立描述的 Skill，分别服务于 UI 系统、视觉评审、知识沉淀与产品决策。安装套件并不意味着每轮都加载全部四个。",
                )} /></p>
                <ul className="skill-ribbon" aria-label="Bundled workflow Skills">
                  {workflowSkills.map((skill) => <li key={skill}>{skill.replace("gloamere-", "")}</li>)}
                </ul>
                <dl className="route-metadata">
                  <div><dt><T value={l("Discovery", "发现")} /></dt><dd><T value={l("Skill description boundary", "Skill 描述边界")} /></dd></div>
                  <div><dt><T value={l("Loading", "加载")} /></dt><dd><T value={l("Only when the task fits", "仅在任务匹配时")} /></dd></div>
                </dl>
                <Link className="text-link" href="/workflows">
                  <T value={l("Explore Gloamere Workflows", "了解 Gloamere Workflows")} />
                </Link>
              </div>
            </article>
          </div>
        </section>

        <section className="proof-section glass">
          <div className="proof-statement">
            <p className="eyebrow"><T value={l("Evidence before verdict", "先有证据，再下结论")} /></p>
            <h2><T value={l("“The model said so” is not proof.", "“模型说它做了”并不是证据。")} /></h2>
          </div>
          <div className="proof-copy">
            <p><T value={l(
              "A verified Eval attempt needs a complete, recognized Codex event stream that agrees with the target lock. Truncated, malformed, or unknown evidence closes without a scored verdict.",
              "一次 verified 评测必须拥有完整、可识别且与目标锁一致的 Codex 事件流。遇到截断、畸形或未知证据时，评测会停止且不给出评分结论。",
            )} /></p>
            <div className="status-equation" aria-label="Evidence rule">
              <code>verified</code><span>→</span><code>pass | fail</code>
              <b><T value={l("otherwise", "否则")} /></b><code>verdict = null</code>
            </div>
            <Link className="text-link" href="/eval#evidence-status">
              <T value={l("Read the evidence contract", "阅读证据契约")} />
            </Link>
          </div>
        </section>

        <BetaBoundary />
        <InstallPanel />

        <section className="closing-section glass">
          <Image src="/gloamere-logo.png" width="160" height="160" alt="" unoptimized />
          <div>
            <p className="eyebrow"><T value={l("Open source, local by design", "开源，并以本地运行为设计前提")} /></p>
            <h2><T value={l("Review the exact release before Codex loads it.", "在 Codex 加载前，检查精确发行内容。")} /></h2>
            <p><T value={l(
              "The repository publishes deterministic plugin archives and SHA-256 sidecars. Gloamere adds no account, analytics endpoint, or hosted runtime.",
              "仓库发布确定性的插件归档与 SHA-256 校验文件。Gloamere 不增加账户、分析端点或托管运行时。",
            )} /></p>
            <a className="button button-secondary" href={REPOSITORY_URL}>
              <T value={l("Inspect the repository", "检查仓库")} />
            </a>
          </div>
        </section>
      </main>
    </SiteFrame>
  );
}
