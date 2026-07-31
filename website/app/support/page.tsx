import type { Metadata } from "next";
import Link from "next/link";
import { T } from "../i18n";
import { l } from "../locale";
import { DIRECTORY_APPROVED } from "../release-state";
import {
  ISSUE_TRACKER_URL,
  PageHero,
  SiteFrame,
} from "../site";

export const metadata: Metadata = {
  title: "Support",
  description: "Directory status, supported surfaces, and reporting guidance for Gloamere Workflows.",
  alternates: { canonical: "/support" },
};

export default function SupportPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={DIRECTORY_APPROVED
              ? l("Support / Official directory", "支持 / 官方目录")
              : l("Support / Directory candidate", "支持 / 目录候选版")}
            title={DIRECTORY_APPROVED
              ? l("Support for the verified listing.", "已验证目录条目的支持。")
              : l("Review in progress. Evidence is welcome.", "审核准备中，欢迎提供证据。")}
            summary={DIRECTORY_APPROVED
              ? l(
                  "Gloamere Workflows is available from the verified official directory listing. Support covers ChatGPT Work on web, ChatGPT Work and Codex desktop apps, and Codex CLI—not Chat, IDE integrations, or mobile.",
                  "Gloamere Workflows 已通过验证的官方目录条目提供。支持范围覆盖 ChatGPT Work 网页端、ChatGPT Work 与 Codex 桌面端，以及 Codex CLI；不包含 Chat、IDE 集成或移动端。",
                )
              : l(
                  "Gloamere Workflows is preparing for official plugin directory review and has no public installation path yet. Once approved, support will cover ChatGPT Work on web, ChatGPT Work and Codex desktop apps, and Codex CLI—not Chat, IDE integrations, or mobile.",
                  "Gloamere Workflows 正在准备官方插件目录审核，目前没有公开安装入口。获批后，支持范围将覆盖 ChatGPT Work 网页端、ChatGPT Work 与 Codex 桌面端，以及 Codex CLI；不包含 Chat、IDE 集成或移动端。",
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
              <h2><T value={l("Make the feedback verifiable.", "让反馈可以被验证。")} /></h2>
              <ol className="support-checklist glass">
                <li><T value={l("State whether the report concerns Product Decision, Visual Review, or Knowledge Capture.", "说明报告涉及产品决策、视觉评审还是知识沉淀。")} /></li>
                <li><T value={l("Describe the expected outcome and the smallest input that reproduces the problem.", "说明期望结果，以及能复现问题的最小输入。")} /></li>
                <li><T value={DIRECTORY_APPROVED
                  ? l("Include the host surface and exact plugin version shown by that host.", "请包含所用宿主端，以及该宿主显示的精确插件版本。")
                  : l("After directory approval, include the host surface and exact plugin version shown by that host.", "目录获批后，请包含所用宿主端，以及该宿主显示的精确插件版本。")} /></li>
                <li><T value={l("Remove secrets, private prompt contents, usernames, absolute local paths, and customer data.", "移除密钥、私密提示词内容、用户名、本地绝对路径和客户数据。")} /></li>
              </ol>
            </article>
            <aside className="support-actions glass">
              <div>
                <p className="eyebrow"><T value={l("Public issue", "公开 Issue")} /></p>
                <h2><T value={l("Workflow behavior, docs, directory status", "工作流行为、文档与目录状态")} /></h2>
                <p><T value={l("Include a minimal reproduction and distinguish observed output from your interpretation. Missing source material is not evidence that a workflow failed.", "请包含最小复现，并区分实际观察到的输出与个人解释。缺少源材料本身不能证明工作流失败。")} /></p>
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
            <p className="eyebrow"><T value={l("Support boundary", "支持边界")} /></p>
            <h2><T value={DIRECTORY_APPROVED
              ? l("Three public workflows.", "三个公开工作流。")
              : l("Three public workflows, after approval.", "获批后的三个公开工作流。")} /></h2>
            <p><T value={l(
              "Unpublished experiments, Eval maintainer tooling, modified forks, legacy plugin identities, Chat, IDE integrations, and mobile are outside ordinary-user support.",
              "未发布实验、Eval 维护者工具、修改后的分支、旧插件标识、Chat、IDE 集成与移动端均不属于普通用户支持范围。",
            )} /></p>
          </section>
        </div>
      </main>
    </SiteFrame>
  );
}
