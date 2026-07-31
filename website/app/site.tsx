"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  LanguageSwitch,
  T,
} from "./i18n";
import { releaseData } from "./generated-release";
import { l, type LocalizedText } from "./locale";
import {
  DIRECTORY_APPROVED,
  DIRECTORY_STATUS,
  DIRECTORY_URL,
} from "./release-state";

export const REPOSITORY_URL = "https://github.com/gloamere/codex-plugins";
export const ISSUE_TRACKER_URL = `${REPOSITORY_URL}/issues`;
export const SECURITY_REPORT_URL = `${REPOSITORY_URL}/security/advisories/new`;

const directoryPlugin = releaseData.plugins.find(
  (plugin) => plugin.publicRole === "directory",
);
const maintainerPlugin = releaseData.plugins.find(
  (plugin) => plugin.publicRole === "maintainer",
);

if (!directoryPlugin || !maintainerPlugin) {
  throw new Error("Generated release data must include directory and maintainer plugins.");
}

const navigation = [
  { href: "/workflows", label: l("Workflows", "工作流") },
  { href: "/support", label: l("Support", "支持") },
];

export function SiteFrame({
  children,
  showFooter = true,
}: {
  children: ReactNode;
  showFooter?: boolean;
}) {
  return (
    <>
      <a className="skip-link" href="#main-content">
        <T value={l("Skip to content", "跳至正文")} />
      </a>
      <SiteHeader />
      {children}
      {showFooter ? <SiteFooter /> : null}
    </>
  );
}

function SiteHeader() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand-link" href="/" aria-label="Gloamere home">
          <span className="brand-wordmark">Gloamere</span>
          <small><T value={l("Evidence-backed product workflows", "证据驱动的产品工作流")} /></small>
        </Link>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>
              <T value={item.label} />
            </Link>
          ))}
        </nav>
        <div className="header-actions">
          <span className="beta-mark">
            <span className="status-dot" />
            <T value={DIRECTORY_STATUS} />
          </span>
          <LanguageSwitch />
          <a href={REPOSITORY_URL}>GitHub</a>
        </div>
      </div>
    </header>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div>
            <strong className="brand-wordmark">Gloamere</strong>
            <p>
              <T value={l("Evidence-backed workflows for product and design leaders.", "面向产品与设计负责人的证据驱动工作流。")} />
            </p>
          </div>
        </div>
        <nav className="footer-nav" aria-label="Footer navigation">
          <Link href="/support"><T value={l("Support", "支持")} /></Link>
          <Link href="/privacy"><T value={l("Privacy", "隐私")} /></Link>
          <Link href="/terms"><T value={l("Terms", "条款")} /></Link>
          <Link href="/security"><T value={l("Security", "安全")} /></Link>
          <a href={REPOSITORY_URL}><T value={l("Source", "源码")} /></a>
        </nav>
        <p className="footer-note">
          <T
            value={l(
              DIRECTORY_APPROVED
                ? "MIT licensed. Available in the official directory. No Gloamere backend or telemetry."
                : "MIT licensed. Official directory candidate. No Gloamere backend or telemetry.",
              DIRECTORY_APPROVED
                ? "MIT 许可。已在官方目录上线。不含 Gloamere 后端或遥测。"
                : "MIT 许可。官方目录候选版。不含 Gloamere 后端或遥测。",
            )}
          />
          {" · "}
          <T
            value={l(
              "Skills-only; no plugin UI or MCP server.",
              "仅包含 Skills；不含插件 UI 或 MCP 服务器。",
            )}
          />
        </p>
      </div>
    </footer>
  );
}

type PageHeroProps = {
  route: LocalizedText;
  title: LocalizedText;
  summary: LocalizedText;
  aside?: ReactNode;
  children?: ReactNode;
};

export function PageHero({
  route,
  title,
  summary,
  aside,
  children,
}: PageHeroProps) {
  return (
    <section className="page-hero">
      <div className="page-hero-copy">
        <p className="route-label"><T value={route} /></p>
        <h1><T value={title} /></h1>
        <p className="hero-summary"><T value={summary} /></p>
        {children}
      </div>
      {aside ? <div className="page-hero-aside">{aside}</div> : null}
    </section>
  );
}

export function HeroActions({
  primaryHref,
  primaryLabel,
}: {
  primaryHref: string;
  primaryLabel: LocalizedText;
}) {
  return (
    <div className="hero-actions">
      <Link className="button button-primary" href={primaryHref}>
        <T value={primaryLabel} />
      </Link>
      <a className="button button-secondary" href={REPOSITORY_URL}>
        <T value={l("Browse source", "浏览源码")} />
      </a>
    </div>
  );
}

export function EvidenceTrace({ compact = false }: { compact?: boolean }) {
  return (
    <figure className={`evidence-trace${compact ? " evidence-trace-compact" : ""}`}>
      <figcaption className="trace-heading">
        <span><T value={l("Native trace ledger", "原生证据账本")} /></span>
        <span className="schema-chip">schema v4 / record 001</span>
      </figcaption>
      <ol className="trace-list">
        <li className="trace-node">
          <span className="trace-step">01 / prompt</span>
          <code>prompt_sha256</code>
          <strong>96f3…d221</strong>
          <small><T value={l("Raw prompt omitted", "默认省略原始提示词")} /></small>
        </li>
        <li className="trace-node">
          <span className="trace-step">02 / target lock</span>
          <code>manifest / Skill / agent SHA</code>
          <strong>gloamere-workflows</strong>
          <small><T value={l("Three path-bound files", "绑定三个文件路径")} /></small>
        </li>
        <li className="trace-node trace-node-result">
          <span className="trace-step">03 / observation</span>
          <code>evidence_status</code>
          <strong>verified</strong>
          <small>verdict <b>pass</b></small>
        </li>
      </ol>
      <p className="trace-disclaimer">
        <T
          value={l(
            "Specimen record: field anatomy only—not a published native-admission result.",
            "样例记录：仅展示字段结构，并非已发布的原生准入结果。",
          )}
        />
      </p>
    </figure>
  );
}

export function EvidenceFlow() {
  const stages = [
    {
      index: "01",
      label: l("Fingerprint the case", "为案例生成指纹"),
      detail: l(
        "Store the prompt hash by default; keep the raw prompt out of the report.",
        "默认保存提示词哈希，不把提示词原文写入报告。",
      ),
      field: "prompt_sha256",
      value: "96f3…d221",
    },
    {
      index: "02",
      label: l("Lock the target", "锁定目标身份"),
      detail: l(
        "Bind plugin ID, version, full Skill path, and file SHA before execution.",
        "执行前绑定插件 ID、版本、完整 Skill 路径与文件 SHA。",
      ),
      field: "target_lock",
      value: "path + SHA-256",
    },
    {
      index: "03",
      label: l("Observe native events", "观察原生事件"),
      detail: l(
        "Read the recognized Codex event stream; incomplete or unknown evidence fails closed.",
        "读取可识别的 Codex 事件流；不完整或未知证据一律关闭评分。",
      ),
      field: "codex_events",
      value: "complete",
    },
    {
      index: "04",
      label: l("Separate evidence from verdict", "分离证据与结论"),
      detail: l(
        "Only verified evidence receives pass or fail. Every other state returns a null verdict.",
        "只有 verified 证据得到 pass 或 fail；其他状态的 verdict 均为 null。",
      ),
      field: "evidence_status",
      value: "verified / pass",
    },
  ];

  return (
    <section className="evidence-flow-section" aria-labelledby="evidence-flow-title">
      <header className="flow-heading">
        <div>
          <p className="eyebrow"><T value={l("Native evidence route", "原生证据路径")} /></p>
          <h2 id="evidence-flow-title">
            <T value={l("A verdict has a chain of custody.", "每个结论都有完整保管链。")} />
          </h2>
        </div>
        <p>
          <T value={l(
            "The sequence is deliberate: identity is fixed before Codex runs, and scoring begins only after the evidence stream is complete.",
            "顺序不可颠倒：先固定身份，再运行 Codex；只有事件证据完整后才开始评分。",
          )} />
        </p>
      </header>

      <div className="flow-sheet">
        <div className="flow-register" aria-hidden="true">
          <span>REGISTER / GM-NATIVE-001</span>
          <span>SCHEMA / V3</span>
          <span>POLICY / FAIL CLOSED</span>
        </div>
        <ol className="flow-main">
          {stages.map((stage) => (
            <li className="flow-stage" key={stage.index}>
              <span className="flow-index">{stage.index}</span>
              <div className="flow-stage-copy">
                <h3><T value={stage.label} /></h3>
                <p><T value={stage.detail} /></p>
              </div>
              <div className="flow-field">
                <code>{stage.field}</code>
                <strong>{stage.value}</strong>
              </div>
            </li>
          ))}
        </ol>

        <div className="flow-exceptions">
          <p className="flow-exception-label">
            <T value={l("Fail-closed exits", "关闭评分出口")} />
          </p>
          <div>
            <span><code>identity_conflict</code><b>verdict = null</b></span>
            <small><T value={l("Lock or installed identity disagrees.", "锁文件与已安装身份不一致。")} /></small>
          </div>
          <div>
            <span><code>unobservable</code><b>verdict = null</b></span>
            <small><T value={l("Event stream is unknown, malformed, or truncated.", "事件流未知、畸形或被截断。")} /></small>
          </div>
        </div>

        <footer className="flow-footnote">
          <span><T value={l("Evidence status", "证据状态")} /> ≠ <T value={l("routing verdict", "路由结论")} /></span>
          <span><T value={l("Illustrative contract, not an admission result.", "契约示意，并非准入结果。")} /></span>
        </footer>
      </div>
    </section>
  );
}

export function InstallPanel({
  plugin = "both",
}: {
  plugin?: "eval" | "workflows" | "both";
}) {
  const isMaintainerTool = plugin === "eval";
  const hasApprovedDirectoryListing =
    !isMaintainerTool && DIRECTORY_APPROVED;

  return (
    <section className="install-section" id="directory-status">
      <div className="section-heading">
        <p className="eyebrow">
          <T value={l(isMaintainerTool ? "Maintainer surface" : "Directory status", isMaintainerTool ? "维护者工具" : "目录状态")} />
        </p>
        <h2>
          <T
            value={
              isMaintainerTool
                ? l(
                    "Eval is not part of the first directory submission.",
                    "Eval 不属于首轮官方目录提交。",
                  )
                : DIRECTORY_STATUS
            }
          />
        </h2>
        <p>
          <T value={l(
            isMaintainerTool
              ? "The evaluation tooling remains available to repository maintainers as internal quality infrastructure."
              : hasApprovedDirectoryListing
                ? "The verified official directory listing is live. Open it below to use Gloamere Workflows."
                : "No installation command is published yet. This page will link to the verified directory listing only after review and approval.",
            isMaintainerTool
              ? "评测工具继续作为仓库维护者使用的内部质量设施。"
              : hasApprovedDirectoryListing
                ? "经过验证的官方目录条目已上线，可通过下方链接使用 Gloamere Workflows。"
                : "目前尚未发布安装命令。审核通过后，本页才会链接到经过验证的目录条目。",
          )} />
        </p>
      </div>
      <div className="install-console" aria-label={isMaintainerTool ? "Maintainer availability" : "Official directory review status"}>
        <div className="console-bar">
          <span><T value={l(isMaintainerTool ? "Repository tooling" : "Official plugin directory", isMaintainerTool ? "仓库工具" : "官方插件目录")} /></span>
          <span>
            {isMaintainerTool
              ? `${maintainerPlugin.displayName} ${maintainerPlugin.version}`
              : `${directoryPlugin.displayName} ${directoryPlugin.version}`}
          </span>
        </div>
        <div className="directory-status-copy">
          <strong>
            <T value={isMaintainerTool ? l("Source available to maintainers", "源码供维护者使用") : DIRECTORY_STATUS} />
          </strong>
          <p>
            <T value={l(
              isMaintainerTool
                ? "There is no ordinary-user installation path for Eval."
                : "Gloamere Workflows is skills-only: no plugin UI, screenshots, MCP server, account, or Gloamere telemetry.",
              isMaintainerTool
                ? "Eval 不提供面向普通用户的安装入口。"
                : "Gloamere Workflows 仅包含 Skills：不含插件 UI、截图、MCP 服务器、账户或 Gloamere 遥测。",
            )} />
          </p>
        </div>
      </div>
      <div className="install-notes">
        <p>
          <strong><T value={l("Supported surfaces:", "支持端：")} /></strong>{" "}
          <T value={l(
            isMaintainerTool
              ? "repository development with Codex CLI."
              : "ChatGPT Work on web, ChatGPT Work and Codex desktop apps, and Codex CLI.",
            isMaintainerTool
              ? "使用 Codex CLI 的仓库开发环境。"
              : "ChatGPT Work 网页端、ChatGPT Work 与 Codex 桌面端，以及 Codex CLI。",
          )} />
        </p>
        <p>
          <strong><T value={l("Not supported:", "不支持：")} /></strong>{" "}
          <T value={l(
            isMaintainerTool ? "ordinary-user support." : "Chat, IDE integrations, or mobile.",
            isMaintainerTool ? "普通用户支持。" : "Chat、IDE 集成或移动端。",
          )} />
        </p>
        {hasApprovedDirectoryListing ? (
          <a href={DIRECTORY_URL ?? "/support"}>
            <T value={l("Open the verified directory listing", "打开已验证的目录条目")} />
          </a>
        ) : (
          <a href={isMaintainerTool ? `${REPOSITORY_URL}/tree/main/plugins/gloamere-eval` : "/support"}>
            <T value={l(isMaintainerTool ? "View maintainer source" : "Read support and review status", isMaintainerTool ? "查看维护者源码" : "查看支持与审核状态")} />
          </a>
        )}
      </div>
    </section>
  );
}

export function BetaBoundary() {
  const items = [
    l("Included", "包含"),
    l("Format", "形态"),
    l("Surfaces", "支持端"),
    l("Status", "状态"),
  ];
  const details = [
    l(
      `${directoryPlugin.skills.length} Skills: Product Decision, Visual Review, and Knowledge Capture.`,
      `${directoryPlugin.skills.length} 个 Skill：产品决策、视觉评审与知识沉淀。`,
    ),
    l("Skills-only, with no plugin UI, screenshots, MCP server, account, or Gloamere backend.", "仅包含 Skills，不含插件 UI、截图、MCP 服务器、账户或 Gloamere 后端。"),
    l("ChatGPT Work web, ChatGPT Work and Codex desktop apps, and Codex CLI; not Chat, IDE integrations, or mobile.", "ChatGPT Work 网页端、ChatGPT Work 与 Codex 桌面端，以及 Codex CLI；不支持 Chat、IDE 集成或移动端。"),
    DIRECTORY_APPROVED
      ? l("Available from the verified official directory listing.", "可通过已验证的官方目录条目使用。")
      : l("Preparing for official directory review. Installation remains unavailable until an approved listing is live.", "正在准备官方目录审核；获批条目上线前不提供安装入口。"),
  ];

  return (
    <aside className="boundary-panel glass" aria-labelledby="directory-boundary-title">
      <div>
        <p className="eyebrow"><T value={l("Directory boundary", "目录边界")} /></p>
        <h2 id="directory-boundary-title"><T value={l("A focused first submission.", "一次聚焦的首轮提交。")} /></h2>
      </div>
      <dl>
        {items.map((item, index) => (
          <div key={item.en}>
            <dt><T value={item} /></dt>
            <dd><T value={details[index]} /></dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

export function LegalPage({
  route,
  title,
  lead,
  children,
}: {
  route: LocalizedText;
  title: LocalizedText;
  lead: LocalizedText;
  children: ReactNode;
}) {
  return (
    <SiteFrame>
      <main id="main-content" className="legal-layout">
        <header className="legal-header">
          <p className="route-label"><T value={route} /></p>
          <h1><T value={title} /></h1>
          <p><T value={lead} /></p>
        </header>
        <article className="legal-copy glass">{children}</article>
      </main>
    </SiteFrame>
  );
}
