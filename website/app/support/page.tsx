import type { Metadata } from "next";
import Link from "next/link";
import { T } from "../i18n";
import { l } from "../locale";
import { RELEASE_PUBLISHED } from "../release-state";
import {
  ISSUE_TRACKER_URL,
  PageHero,
  SiteFrame,
} from "../site";

export const metadata: Metadata = {
  title: "Support",
  description: "Git marketplace status, intended targets, and reporting guidance for Gloamere Workflows.",
  alternates: { canonical: "/support" },
};

export default function SupportPage() {
  return (
    <SiteFrame>
      <main id="main-content">
        <div className="page-wrap">
          <PageHero
            route={l("Support / Git marketplace", "支持 / Git marketplace")}
            title={RELEASE_PUBLISHED
              ? l("Support for the tagged marketplace release.", "带标签 marketplace 发布版的支持。")
              : l("Reproduce first. Keep reports private where needed.", "先复现，必要时私下报告。")}
            summary={RELEASE_PUBLISHED
              ? l(
                  "The intended repository-marketplace targets are the ChatGPT desktop plugin surface and Codex CLI. It does not claim self-hosted installation on ChatGPT Work web, Chat, IDE integrations, or mobile.",
                  "仓库 marketplace 的预期目标是 ChatGPT 桌面端插件界面与 Codex CLI；不承诺 ChatGPT Work 网页端、Chat、IDE 集成或移动端的自托管安装。",
                )
              : l(
                  "The v4.0.0 tag is not published yet, so remote installation is not live. The intended targets are the ChatGPT desktop plugin surface and Codex CLI, but desktop compatibility still requires a release-candidate smoke test. It does not claim self-hosted installation on ChatGPT Work web, Chat, IDE integrations, or mobile.",
                  "v4.0.0 标签尚未发布，因此远程安装尚未开放。预期目标是 ChatGPT 桌面端插件界面与 Codex CLI，但桌面兼容性仍需发布候选烟测；不承诺 ChatGPT Work 网页端、Chat、IDE 集成或移动端的自托管安装。",
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
                <li><T value={l("Include the installation source, host surface, and exact plugin version shown by that host.", "请包含安装来源、所用宿主端，以及该宿主显示的精确插件版本。")} /></li>
                <li><T value={l("Remove secrets, private prompt contents, usernames, absolute local paths, and customer data.", "移除密钥、私密提示词内容、用户名、本地绝对路径和客户数据。")} /></li>
              </ol>
            </article>
            <aside className="support-actions glass">
              <div>
                <p className="eyebrow"><T value={l("Public issue", "公开 Issue")} /></p>
                <h2><T value={l("Workflow behavior, docs, marketplace installation", "工作流行为、文档与 marketplace 安装")} /></h2>
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
            <h2><T value={l("Three public workflows.", "三个公开工作流。")} /></h2>
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
