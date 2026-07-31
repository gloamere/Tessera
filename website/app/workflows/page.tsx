import type { Metadata } from "next";
import { releaseData } from "../generated-release";
import { T } from "../i18n";
import { l } from "../locale";
import { DIRECTORY_APPROVED } from "../release-state";
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
    "Three evidence-backed Skills for product decisions, visual review, and durable knowledge.",
  alternates: { canonical: "/workflows" },
};

const workflowPlugin = releaseData.plugins.find(
  (plugin) => plugin.publicRole === "directory",
);

if (!workflowPlugin) {
  throw new Error("Generated release data must include a directory plugin.");
}

const skillCatalog = [
  {
    id: "gloamere-product-decision",
    anchor: "product-decision",
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
    status: l(`${workflowPlugin.version} · Gloamere-authored`, `${workflowPlugin.version} · Gloamere 原创`),
  },
  {
    id: "gloamere-visual-review",
    anchor: "visual-review",
    title: l("Visual Review", "视觉评审"),
    trigger: l(
      "An existing interface, screenshot, design draft, component, or visual artifact needs an evidence-backed review.",
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
    status: l(`${workflowPlugin.version} · Gloamere-authored`, `${workflowPlugin.version} · Gloamere 原创`),
  },
  {
    id: "gloamere-knowledge-capture",
    anchor: "knowledge-capture",
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
    status: l(`${workflowPlugin.version} · Gloamere-authored`, `${workflowPlugin.version} · Gloamere 原创`),
  },
];

const releaseSkillIds = new Set<string>(workflowPlugin.skills);
const skills = skillCatalog.filter((skill) => releaseSkillIds.has(skill.id));

if (skills.length !== workflowPlugin.skills.length) {
  throw new Error("Generated release data includes a Skill without website copy.");
}

export default function WorkflowsPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={DIRECTORY_APPROVED
              ? l("Official directory / Workflows", "官方目录 / 工作流")
              : l("Official directory candidate / Workflows", "官方目录候选 / 工作流")}
            title={l("Decide. Review. Preserve.", "决策、评审、沉淀。")}
            summary={l(
              "Gloamere Workflows gives product and design leaders three focused Skills with explicit trigger and exclusion boundaries. Each one turns available evidence into a concrete next step.",
              "Gloamere Workflows 为产品与设计负责人提供三个聚焦 Skill，并明确触发与排除边界。每个 Skill 都把已有证据转化为具体的下一步。",
            )}
            aside={
              <div className="workflow-orbit glass" aria-label="Three workflow Skills">
                <div className="orbit-core"><T value={l("task", "任务")} /></div>
                <span className="orbit-item orbit-decision">decision</span>
                <span className="orbit-item orbit-review">visual review</span>
                <span className="orbit-item orbit-knowledge">knowledge</span>
              </div>
            }
          >
            <HeroActions primaryHref="#directory-status" primaryLabel={l("Check directory status", "查看目录状态")} />
          </PageHero>

          <section className="skill-section">
            <div className="section-heading">
              <p className="eyebrow"><T value={l("Focused Skill surface", "聚焦的 Skill 界面")} /></p>
              <h2><T value={l("One product loop. Three clear jobs.", "一个产品闭环，三个明确任务。")} /></h2>
              <p><T value={l(
                "The Skills do not invent research or load as a bundle. The host uses each description and the user’s request to discover only the relevant workflow.",
                "这些 Skill 不会虚构研究，也不会整包加载。宿主会结合每项描述与用户请求，只发现相关的工作流。",
              )} /></p>
            </div>
            <div className="skill-index">
              {skills.map((skill) => (
                <article key={skill.id} id={skill.anchor} className="skill-entry glass">
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
              <p className="eyebrow"><T value={l("Evidence-backed by design", "以证据为设计前提")} /></p>
              <h2><T value={l("The workflow follows the life of a decision.", "工作流跟随一项决策的生命周期。")} /></h2>
            </div>
            <div className="provenance-ledger">
              <article>
                <span className="ledger-mark">01 / decide</span>
                <h3><T value={l("Choose with what is known", "基于已知信息做选择")} /></h3>
                <p><T value={l(
                  "Product Decision separates evidence, assumptions, options, tradeoffs, and the next validation before scope hardens.",
                  "产品决策在范围固化前，分离证据、假设、选项、权衡与下一步验证。",
                )} /></p>
              </article>
              <article>
                <span className="ledger-mark">02 / review</span>
                <h3><T value={l("Inspect what actually exists", "检查真实存在的产物")} /></h3>
                <p><T value={l(
                  "Visual Review anchors observations to an inspectable artifact, then limits recommendations to the changes with the highest user impact.",
                  "视觉评审把观察锚定到可检查的产物，再将建议限制在用户影响最高的改动上。",
                )} /></p>
              </article>
              <article>
                <span className="ledger-mark ledger-gate">03 / preserve</span>
                <h3><T value={l("Keep the reasoning usable", "让推理持续可用")} /></h3>
                <p><T value={l(
                  "Knowledge Capture preserves sources, decisions, ownership, and open questions in the structure of the target knowledge base.",
                  "知识沉淀按目标知识库的结构保留来源、决策、负责人和开放问题。",
                )} /></p>
              </article>
            </div>
            <a className="text-link" href={`${REPOSITORY_URL}/tree/main/plugins/gloamere-workflows`}>
              <T value={l("Review the public Skill source", "查看公开 Skill 源码")} />
            </a>
          </section>

          <BetaBoundary />

          <section className="experiment-note glass">
            <span>LAB ≠ RELEASE</span>
            <div>
              <h2><T value={l("Experiments stay outside the plugin.", "实验始终留在插件之外。")} /></h2>
              <p><T value={l(
                "Repository labs may explore future workflows and maintainer tooling, but they are not bundled, supported, or presented as part of the first official-directory submission.",
                "仓库实验区可以探索未来工作流与维护者工具，但它们不会被打包、支持或呈现为首轮官方目录提交的一部分。",
              )} /></p>
            </div>
          </section>
        </div>
        <InstallPanel plugin="workflows" />
      </main>
    </SiteFrame>
  );
}
