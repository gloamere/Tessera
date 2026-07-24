import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { BetaBoundary, HeroActions, InstallPanel, PageHero, REPOSITORY_URL, SiteFrame } from "../site";

export const metadata: Metadata = {
  title: "Gloamere Workflows",
  description:
    "Four focused Codex Skills for UI systems, visual review, durable knowledge, and product decisions.",
  alternates: { canonical: "/workflows" },
};

const skills = [
  {
    id: "gloamere-ui-system",
    title: l("UI System", "UI 系统"),
    trigger: l(
      "New UI, systematic redesign, design tokens, responsive behavior, or implementation constraints.",
      "新 UI、系统性重设计、设计令牌、响应式行为或实现约束。",
    ),
    output: l(
      "A coherent direction, token system, layout and state rules, accessibility boundaries, and stack-aware implementation guidance.",
      "一致的设计方向、令牌系统、布局与状态规则、无障碍边界，以及贴合技术栈的实现指引。",
    ),
    boundary: l(
      "Not for backend-only work, isolated functional bugs, copy editing, user research, or conversion experiments.",
      "不用于纯后端工作、孤立功能 Bug、文案编辑、用户研究或转化实验。",
    ),
    status: l("Stable Skill identity · Beta vendor core", "稳定 Skill 标识 · Beta vendor core"),
  },
  {
    id: "gloamere-visual-review",
    title: l("Visual Review", "视觉评审"),
    trigger: l(
      "An existing interface, screenshot, design draft, component, or visual artifact needs an evidence-led review.",
      "已有界面、截图、设计稿、组件或视觉产物需要基于证据的评审。",
    ),
    output: l(
      "Visible observations, their user impact, up to three prioritized changes, and a concrete validation method.",
      "可见观察、对用户的影响、最多三项优先改动，以及具体的验证方法。",
    ),
    boundary: l(
      "Not for creating a system from zero, text-only polish, or design advice without an inspectable artifact.",
      "不用于从零创建系统、纯文字润色，或在没有可检查产物时提供设计建议。",
    ),
    status: l("Stable Skill identity · Gloamere-authored", "稳定 Skill 标识 · Gloamere 原创"),
  },
  {
    id: "gloamere-knowledge-capture",
    title: l("Knowledge Capture", "知识沉淀"),
    trigger: l(
      "A conversation, research set, operating lesson, or project decision should become maintainable Markdown knowledge.",
      "对话、研究资料、运营经验或项目决策需要转化为可维护的 Markdown 知识。",
    ),
    output: l(
      "De-duplicated, linked records that preserve sources, status, dates, ownership, and open questions.",
      "去重并相互链接的记录，保留来源、状态、日期、负责人和开放问题。",
    ),
    boundary: l(
      "Not for transient chat summaries, generic prose editing, or a one-off answer with no target knowledge base.",
      "不用于临时聊天摘要、通用文章编辑，或没有目标知识库的一次性回答。",
    ),
    status: l("Stable Skill identity · Gloamere-authored", "稳定 Skill 标识 · Gloamere 原创"),
  },
  {
    id: "gloamere-product-decision",
    title: l("Product Decision", "产品决策"),
    trigger: l(
      "Existing research, data, and constraints need to converge into a scoped product choice.",
      "已有研究、数据与约束需要收敛成边界明确的产品选择。",
    ),
    output: l(
      "A recommendation, evidence ledger, alternatives, tradeoffs, success measures, risks, open questions, and the next validation.",
      "建议、证据账本、备选方案、权衡、成功指标、风险、开放问题与下一步验证。",
    ),
    boundary: l(
      "Not for pretending research occurred, growth execution, internal operations, or implementation planning after the choice is made.",
      "不用于假装已经研究、增长执行、内部运营，或决策完成后的实现规划。",
    ),
    status: l("Stable Skill identity · Gloamere-authored", "稳定 Skill 标识 · Gloamere 原创"),
  },
];

export default function WorkflowsPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={l("Plugin route / Workflows", "插件路径 / 工作流")}
            title={l("Four workflows. Loaded only when the task fits.", "四个工作流，只在任务匹配时加载。")}
            summary={l(
              "Gloamere Workflows adds four stable Skill identities with explicit trigger and exclusion boundaries. The bundle is installed once; Codex still decides which matching Skill to load.",
              "Gloamere Workflows 提供四个稳定 Skill 标识，并明确触发与排除边界。套件只需安装一次，Codex 仍会判断应加载哪个匹配 Skill。",
            )}
            aside={
              <div className="workflow-orbit glass" aria-label="Four workflow Skills">
                <div className="orbit-core"><T value={l("task", "任务")} /></div>
                <span className="orbit-item orbit-ui">UI system</span>
                <span className="orbit-item orbit-review">visual review</span>
                <span className="orbit-item orbit-knowledge">knowledge</span>
                <span className="orbit-item orbit-decision">decision</span>
              </div>
            }
          >
            <HeroActions primaryHref="#install" primaryLabel={l("Install Gloamere Workflows", "安装 Gloamere Workflows")} />
          </PageHero>

          <section className="skill-section">
            <div className="section-heading">
              <p className="eyebrow"><T value={l("Stable Skill surface", "稳定 Skill 界面")} /></p>
              <h2><T value={l("Each route earns its turn.", "每条路径都必须证明自己值得被调用。")} /></h2>
              <p><T value={l(
                "Installation does not preload all four workflows. Codex uses their descriptions and the user’s request to discover the relevant route.",
                "安装不会预加载全部四个工作流。Codex 会结合各自描述与用户请求发现相关路径。",
              )} /></p>
            </div>
            <div className="skill-index">
              {skills.map((skill) => (
                <article key={skill.id} className="skill-entry glass">
                  <header>
                    <p className="plugin-id">{skill.id}</p>
                    <h3><T value={skill.title} /></h3>
                    <span className="skill-status"><T value={skill.status} /></span>
                  </header>
                  <dl>
                    <div><dt><T value={l("Use when", "适用场景")} /></dt><dd><T value={skill.trigger} /></dd></div>
                    <div><dt><T value={l("Produces", "产出")} /></dt><dd><T value={skill.output} /></dd></div>
                    <div><dt><T value={l("Boundary", "边界")} /></dt><dd><T value={skill.boundary} /></dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          <section className="provenance-section">
            <div className="provenance-title">
              <p className="eyebrow"><T value={l("Provenance is part of the product", "来源信息也是产品的一部分")} /></p>
              <h2><T value={l("Original workflow contracts. One isolated vendor core.", "原创工作流契约，一个隔离的 vendor core。")} /></h2>
            </div>
            <div className="provenance-ledger">
              <article>
                <span className="ledger-mark">original</span>
                <h3><T value={l("Three Gloamere-authored Skills", "三个 Gloamere 原创 Skill")} /></h3>
                <p><T value={l(
                  "Visual Review, Knowledge Capture, and Product Decision were rewritten around Gloamere’s own route boundaries, output contracts, and failure cases.",
                  "视觉评审、知识沉淀与产品决策均围绕 Gloamere 自有路由边界、输出契约与失败案例重写。",
                )} /></p>
              </article>
              <article>
                <span className="ledger-mark">isolated</span>
                <h3><T value={l("UI System vendor core", "UI 系统 vendor core")} /></h3>
                <p><T value={l(
                  "The GitHub beta candidate contains a pinned MIT UI data and helper core. Its exact file boundary, upstream commit, adjustment, and complete license notice are preserved.",
                  "GitHub Beta 候选版包含固定版本的 MIT UI 数据与辅助核心；其精确文件边界、上游提交、调整和完整许可证声明均被保留。",
                )} /></p>
              </article>
              <article>
                <span className="ledger-mark ledger-gate">GA gate</span>
                <h3><T value={l("Original replacement required", "必须完成原创替换")} /></h3>
                <p><T value={l(
                  "Official-directory GA remains gated on replacing that vendor core with Gloamere-owned taxonomy, data, scripts, and rules, then rerunning identity, routing, and quality evaluations.",
                  "官方目录 GA 仍以替换 vendor core 为门禁：使用 Gloamere 自有分类、数据、脚本与规则，并重新运行身份、路由和质量评测。",
                )} /></p>
              </article>
            </div>
            <a className="text-link" href={`${REPOSITORY_URL}/blob/main/plugins/gloamere-workflows/PROVENANCE.md`}>
              <T value={l("Read the full provenance record", "阅读完整来源记录")} />
            </a>
          </section>

          <BetaBoundary />

          <section className="experiment-note glass">
            <span>LAB ≠ RELEASE</span>
            <div>
              <h2><T value={l("Experiments stay outside the plugin.", "实验始终留在插件之外。")} /></h2>
              <p><T value={l(
                "Repository labs may explore future workflows, but they are not bundled, supported, or presented as release Skills. Finance, growth, and general business-operations Skills are also outside the 4.0 beta candidate.",
                "仓库实验区可以探索未来工作流，但不会被打包、支持或呈现为发布 Skill。财务、增长与通用业务运营 Skill 同样不属于 4.0 Beta 候选版。",
              )} /></p>
            </div>
          </section>
        </div>
        <InstallPanel plugin="workflows" />
      </main>
    </SiteFrame>
  );
}
