import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { EvidenceTrace, HeroActions, InstallPanel, PageHero, SiteFrame } from "../site";

export const metadata: Metadata = {
  title: "Gloamere Eval",
  description:
    "Internal maintainer tooling for inspecting and evaluating native Codex Skill activation.",
  alternates: { canonical: "/eval" },
  robots: { index: false, follow: false },
};

const evidenceStates = [
  {
    state: "verified",
    meaning: l(
      "The recognized Codex event stream is complete, agrees with the model statement, and resolves to the locked Skill path.",
      "可识别的 Codex 事件流完整、与模型声明一致，并解析到锁定的 Skill 路径。",
    ),
    verdict: "pass or fail",
  },
  {
    state: "unobservable",
    meaning: l(
      "The event stream is malformed, truncated, or contains an unknown event.",
      "事件流畸形、被截断，或包含未知事件。",
    ),
    verdict: "null",
  },
  {
    state: "unavailable",
    meaning: l(
      "Codex, the plugin directory, or an enabled target cannot currently be observed.",
      "当前无法观察 Codex、插件目录或已启用的目标。",
    ),
    verdict: "null",
  },
  {
    state: "identity_conflict",
    meaning: l(
      "The model statement, duplicate Skill name, installed identity, or target lock disagree.",
      "模型声明、重复 Skill 名称、已安装身份或目标锁之间存在冲突。",
    ),
    verdict: "null",
  },
  {
    state: "execution_error",
    meaning: l(
      "Codex or the event adapter did not complete successfully.",
      "Codex 或事件适配器未成功完成。",
    ),
    verdict: "null",
  },
];

export default function EvalPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={l("Plugin route / Eval", "插件路径 / 评测")}
            title={l("Measure what Codex actually loaded.", "评测 Codex 实际加载了什么。")}
            summary={l(
              "Gloamere Eval binds the plugin manifest, Skill, and agent configuration to exact paths and SHAs before observing native Codex activation. Evidence gaps stay visible instead of becoming false accuracy.",
              "Gloamere Eval 先把插件清单、Skill 与 agent 配置绑定到精确路径和 SHA，再观察原生 Codex 调用。证据缺口会被明确呈现，而不会变成虚假的准确率。",
            )}
            aside={<EvidenceTrace compact />}
          >
            <HeroActions primaryHref="#directory-status" primaryLabel={l("View maintainer status", "查看维护者状态")} />
          </PageHero>

          <section className="method-section">
            <div className="section-heading">
              <p className="eyebrow"><T value={l("Three explicit actions", "三个明确动作")} /></p>
              <h2><T value={l("Lock, validate, observe.", "锁定、校验、观察。")} /></h2>
              <p><T value={l(
                "The runner uses Python 3.10+ standard library code and local Codex CLI execution. Each action has a separate responsibility.",
                "运行器使用 Python 3.10+ 标准库与本地 Codex CLI，每个动作承担独立职责。",
              )} /></p>
            </div>
            <ol className="method-list">
              <li className="glass">
                <span className="method-command">inspect</span>
                <div>
                  <h3><T value={l("Lock the installed identity.", "锁定已安装身份。")} /></h3>
                  <p><T value={l(
                    "Record plugin ID and version, installed and enabled state, plus path-bound SHA-256 values for the manifest, Skill, and agent configuration.",
                    "记录插件 ID、版本、安装与启用状态，以及清单、Skill 和 agent 配置绑定路径后的 SHA-256。",
                  )} /></p>
                </div>
              </li>
              <li className="glass">
                <span className="method-command">lint</span>
                <div>
                  <h3><T value={l("Reject drift before execution.", "在执行前拒绝漂移。")} /></h3>
                  <p><T value={l(
                    "Validate the suite, target lock, or report, then reread the target to catch content or identity changes.",
                    "校验 suite、目标锁或报告，再重新读取目标以发现内容或身份变化。",
                  )} /></p>
                </div>
              </li>
              <li className="glass">
                <span className="method-command">native</span>
                <div>
                  <h3><T value={l("Observe Codex’s event stream.", "观察 Codex 事件流。")} /></h3>
                  <p>
                    <T value={l("Run normal activation through ", "通过 ")} />
                    <code>codex exec --json</code>
                    <T value={l(" and verify the actual ", " 运行正常调用，并验证实际 ")} />
                    <code>SKILL.md</code>
                    <T value={l(" path. Unknown or incomplete events fail closed.", " 路径。未知或不完整事件一律关闭评分。")} />
                  </p>
                </div>
              </li>
            </ol>
          </section>

          <section className="evidence-section" id="evidence-status">
            <div className="section-heading">
              <p className="eyebrow"><T value={l("Evidence contract", "证据契约")} /></p>
              <h2><T value={l("Coverage and accuracy stay separate.", "证据覆盖率与准确率保持分离。")} /></h2>
              <p>
                <T value={l("Only ", "只有 ")} /><code>verified</code>
                <T value={l(" observations receive a routing verdict. Every other state explains why scoring is unavailable and returns ", " 观察结果才会得到路由结论；其他状态会解释为何无法评分，并返回 ")} />
                <code>verdict = null</code>.
              </p>
            </div>
            <div className="evidence-table-wrap glass">
              <table className="evidence-table">
                <thead><tr>
                  <th scope="col">evidence_status</th>
                  <th scope="col"><T value={l("What it means", "含义")} /></th>
                  <th scope="col">verdict</th>
                </tr></thead>
                <tbody>
                  {evidenceStates.map((item) => (
                    <tr key={item.state}>
                      <th scope="row"><code>{item.state}</code></th>
                      <td><T value={item.meaning} /></td>
                      <td><code>{item.verdict}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="not-result-note glass">
              <strong><T value={l("No admission claim.", "不作准入声明。")} /></strong>
              <p><T value={l(
                "This page describes the public evaluation contract. It does not claim that Gloamere has passed an official native-admission or directory review.",
                "本页描述公开评测契约，并不声称 Gloamere 已通过官方原生准入或目录审核。",
              )} /></p>
            </aside>
          </section>

          <section className="privacy-by-default">
            <div>
              <p className="eyebrow"><T value={l("Report privacy", "报告隐私")} /></p>
              <h2><T value={l("Hash the prompt. Keep the path local.", "哈希提示词，路径留在本地。")} /></h2>
            </div>
            <ul className="glass">
              <li><T value={l("Reports store the prompt SHA-256 by default, not the raw prompt.", "报告默认保存提示词 SHA-256，而非原始提示词。")} /></li>
              <li><T value={l("Raw prompts require an explicit ", "保存原始提示词需要显式选择 ")} /><code>--include-prompts</code><T value={l(" choice after reviewing the privacy boundary.", "，并先审阅隐私边界。")} /></li>
              <li><T value={l("Reports do not copy absolute paths from the target lock.", "报告不会复制目标锁中的绝对路径。")} /></li>
              <li><T value={l("JSON goes to stdout unless the user supplies ", "除非用户提供 ")} /><code>--output</code><T value={l(".", "，否则 JSON 仅输出到 stdout。")} /></li>
            </ul>
          </section>

          <section className="scope-grid">
            <article className="glass">
              <p className="eyebrow"><T value={l("Designed to do", "设计目标")} /></p>
              <h2><T value={l("Inspect routing evidence.", "检查路由证据。")} /></h2>
              <ul className="check-list">
                <li><T value={l("Evaluate native Codex Skill activation.", "评测原生 Codex Skill 调用。")} /></li>
                <li><T value={l("Surface duplicate names and identity drift.", "暴露重名与身份漂移。")} /></li>
                <li><T value={l("Produce reproducible schema v4 reports.", "生成可复现的 schema v4 报告。")} /></li>
                <li><T value={l("Read historical schema v3 reports without treating them as release evidence.", "只读兼容历史 schema v3 报告，且不将其作为发布证据。")} /></li>
              </ul>
            </article>
            <article className="glass">
              <p className="eyebrow"><T value={l("Designed not to do", "明确不做")} /></p>
              <h2><T value={l("Change the system under test.", "改变被测系统。")} /></h2>
              <ul className="cross-list">
                <li><T value={l("Does not execute the task written inside a test case.", "不执行测试案例中写入的任务。")} /></li>
                <li><T value={l("Does not edit Skills or install dependencies.", "不编辑 Skill 或安装依赖。")} /></li>
                <li><T value={l("Does not treat model self-report as loading evidence.", "不把模型自报当作加载证据。")} /></li>
                <li><T value={l("Does not bundle a business-specific benchmark suite.", "不捆绑特定业务评测套件。")} /></li>
              </ul>
            </article>
          </section>
        </div>
        <InstallPanel plugin="eval" />
      </main>
    </SiteFrame>
  );
}
