"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  LanguageSwitch,
  T,
} from "./i18n";
import { l, type LocalizedText } from "./locale";

export const REPOSITORY_URL = "https://github.com/gloamere/codex-plugins";
export const ISSUE_TRACKER_URL = `${REPOSITORY_URL}/issues`;
export const SECURITY_REPORT_URL = `${REPOSITORY_URL}/security/advisories/new`;
export const RELEASE_TAG = "v4.0.0-beta.1";

const navigation = [
  { href: "/eval", label: l("Eval", "评测") },
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
          <small><T value={l("Evidence-led Codex tools", "为 Codex 构建的证据驱动工具")} /></small>
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
            4.0 Beta / Codex only
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
              <T value={l("Evidence-led tools for Codex.", "为 Codex 构建的证据驱动工具。")} />
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
              "MIT licensed. Beta candidate. No Gloamere backend or telemetry.",
              "MIT 许可。Beta 候选版。不含 Gloamere 后端或遥测。",
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
        <span className="schema-chip">schema v3 / record 001</span>
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
  const pluginCommands =
    plugin === "eval"
      ? ["codex plugin add gloamere-eval@gloamere"]
      : plugin === "workflows"
        ? ["codex plugin add gloamere-workflows@gloamere"]
        : [
            "codex plugin add gloamere-eval@gloamere",
            "codex plugin add gloamere-workflows@gloamere",
          ];

  return (
    <section className="install-section" id="install">
      <div className="section-heading">
        <p className="eyebrow"><T value={l("Pinned installation", "固定版本安装")} /></p>
        <h2><T value={l("Install only after the immutable beta tag is published.", "仅在不可变 Beta 标签发布后安装。")} /></h2>
        <p>
          <T value={l(
            "These commands become valid only after the release gate passes and the exact tag is published. Nothing is fetched from a moving branch.",
            "这些命令只会在发布门禁通过且精确标签发布后生效，不会从持续变化的分支拉取内容。",
          )} />
        </p>
      </div>
      <div className="install-console" aria-label="Installation commands">
        <div className="console-bar">
          <span>Codex CLI</span>
          <span>{RELEASE_TAG}</span>
        </div>
        <pre>
          <code>
            <span>codex plugin marketplace add gloamere/codex-plugins --ref {RELEASE_TAG}</span>
            {pluginCommands.map((command) => <span key={command}>{command}</span>)}
            <span>codex plugin list --json</span>
          </code>
        </pre>
      </div>
      <div className="install-notes">
        <p><strong><T value={l("Default installer:", "默认安装器：")} /></strong>{" "}<T value={l("installs Gloamere Eval.", "安装 Gloamere Eval。")} /></p>
        <p><strong><T value={l("Legacy safety:", "旧版安全：")} /></strong>{" "}<T value={l("detects old 3.x selectors but never removes, disables, or modifies them.", "检测旧 3.x 标识，但绝不会删除、禁用或修改。")} /></p>
        <a href={`${REPOSITORY_URL}#install-the-pinned-beta`}>
          <T value={l("PowerShell, macOS, and Linux installer commands", "PowerShell、macOS 与 Linux 安装命令")} />
        </a>
      </div>
    </section>
  );
}

export function BetaBoundary() {
  const items = [
    l("Prepared", "已准备"),
    l("Isolated", "已隔离"),
    l("Not shipped", "不发布"),
    l("GA gate", "GA 门禁"),
  ];
  const details = [
    l("Two Codex-only plugins and four stable workflow Skill identities; the release tag remains gated on current native evidence.", "两个 Codex-only 插件和四个稳定工作流 Skill 标识；发布标签仍取决于当前原生证据。"),
    l("The UI System beta includes a pinned MIT vendor core with preserved notices and an explicit file boundary.", "UI 系统 Beta 包含固定版本的 MIT vendor core，并保留完整声明与明确文件边界。"),
    l("Repository experiments and finance, growth, or general business-operations Skills.", "仓库实验，以及财务、增长和通用业务运营 Skill。"),
    l("Official-directory GA requires replacing the UI vendor core with Gloamere-owned taxonomy, data, scripts, and rules, then rerunning evaluations at the new SHA.", "官方目录 GA 前必须以 Gloamere 自有分类、数据、脚本和规则替换 UI vendor core，并在新 SHA 上重新评测。"),
  ];

  return (
    <aside className="boundary-panel glass" aria-labelledby="beta-boundary-title">
      <div>
        <p className="eyebrow"><T value={l("Release boundary", "发布边界")} /></p>
        <h2 id="beta-boundary-title"><T value={l("What the 4.0 Beta candidate contains.", "4.0 Beta 候选版包含什么。")} /></h2>
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
