import type { Metadata } from "next";
import Link from "next/link";
import { T } from "../i18n";
import { l } from "../locale";
import { ISSUE_TRACKER_URL, PageHero, SiteFrame } from "../site";

export const metadata: Metadata = {
  title: "Support",
  description: "Support scope and reporting guidance for the Gloamere 4.0 beta candidate.",
  alternates: { canonical: "/support" },
};

export default function SupportPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={l("Support / Beta candidate", "支持 / Beta 候选版")}
            title={l("Bring the smallest safe reproduction.", "提供最小且安全的复现。")}
            summary={l(
              "Before the beta tag is published, support covers release-candidate review. After publication it covers that exact Gloamere Eval and Workflows tag on Codex App, CLI, and IDE. Eval 4.0 supports local Codex CLI execution only.",
              "Beta 标签发布前，支持范围是候选版评审；发布后，覆盖该精确标签在 Codex App、CLI 与 IDE 中的 Gloamere Eval 和 Workflows。Eval 4.0 仅支持本地 Codex CLI 执行。",
            )}
            aside={
              <div className="support-signal glass">
                <span><T value={l("report", "报告")} /></span>
                <strong><T value={l("reproduce", "复现")} /></strong>
                <strong><T value={l("redact", "脱敏")} /></strong>
                <strong><T value={l("identify", "识别")} /></strong>
                <span><T value={l("resolve", "解决")} /></span>
              </div>
            }
          />

          <section className="support-grid">
            <article>
              <p className="eyebrow"><T value={l("Before opening a report", "提交报告之前")} /></p>
              <h2><T value={l("Make the environment observable.", "让环境可以被观察。")} /></h2>
              <ol className="support-checklist glass">
                <li><T value={l("Record the exact Gloamere tag, plugin version, Codex version, operating system, and Python version when Eval is involved.", "记录精确的 Gloamere 标签、插件版本、Codex 版本、操作系统；涉及 Eval 时还需记录 Python 版本。")} /></li>
                <li><T value={l("Reproduce the issue in a new Codex task.", "在新的 Codex 任务中复现问题。")} /></li>
                <li><T value={l("Run ", "运行 ")} /><code>codex plugin list --json</code><T value={l(" and confirm the intended plugin is installed and enabled.", " 并确认目标插件已安装且启用。")} /></li>
                <li><T value={l("Remove secrets, prompt contents, usernames, and absolute local paths from logs or reports.", "从日志或报告中移除密钥、提示词内容、用户名和本地绝对路径。")} /></li>
              </ol>
            </article>
            <aside className="support-actions glass">
              <div>
                <p className="eyebrow"><T value={l("Public issue", "公开 Issue")} /></p>
                <h2><T value={l("Bugs, docs, installation, features", "Bug、文档、安装与功能")} /></h2>
                <p><T value={l("Include a minimal reproduction and the relevant ", "请包含最小复现与相关 ")} /><code>evidence_status</code><T value={l(". An ", "。")} /><code>unobservable</code><T value={l(" result is not automatically a routing failure.", " 结果并不自动等于路由失败。")} /></p>
                <a className="button button-primary" href={ISSUE_TRACKER_URL}>
                  <T value={l("Open the issue tracker", "打开 Issue Tracker")} />
                </a>
              </div>
              <div>
                <p className="eyebrow"><T value={l("Security issue", "安全问题")} /></p>
                <h2><T value={l("Report privately", "私下报告")} /></h2>
                <p><T value={l("Suspected vulnerabilities must not be posted to the public issue tracker.", "疑似漏洞不得发布到公开 Issue Tracker。")} /></p>
                <Link className="button button-secondary" href="/security">
                  <T value={l("Read security reporting", "阅读安全报告方式")} />
                </Link>
              </div>
            </aside>
          </section>

          <section className="support-boundary glass">
            <p className="eyebrow"><T value={l("Outside support scope", "支持范围之外")} /></p>
            <h2><T value={l("Keep experiments and old identities separate.", "将实验与旧身份明确分离。")} /></h2>
            <p><T value={l(
              "Gloamere does not provide support for unpublished experimental workflows, modified forks, old plugin identities, or compatibility with non-Codex hosts.",
              "Gloamere 不为未发布实验工作流、修改后的分支、旧插件身份或非 Codex 宿主兼容性提供支持。",
            )} /></p>
          </section>
        </div>
      </main>
    </SiteFrame>
  );
}
