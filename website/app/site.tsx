"use client";

import Image from "next/image";
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

export function SiteFrame({ children }: { children: ReactNode }) {
  return (
    <>
      <a className="skip-link" href="#main-content">
        <T value={l("Skip to content", "跳至正文")} />
      </a>
      <SiteHeader />
      {children}
      <SiteFooter />
    </>
  );
}

function SiteHeader() {
  return (
    <header className="site-header">
      <div className="header-inner glass">
        <Link className="brand-link" href="/" aria-label="Gloamere home">
          <Image
            className="brand-icon"
            src="/gloamere-icon.png"
            width="34"
            height="34"
            alt=""
            unoptimized
          />
          <span>Gloamere</span>
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
            4.0 Beta
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
          <Image
            src="/gloamere-icon.png"
            width="28"
            height="28"
            alt=""
            unoptimized
          />
          <div>
            <strong>Gloamere</strong>
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
    <figure className={`evidence-trace glass${compact ? " evidence-trace-compact" : ""}`}>
      <div className="lens-glow" aria-hidden="true" />
      <figcaption className="trace-heading">
        <span><T value={l("Evidence lens", "证据透镜")} /></span>
        <span className="schema-chip">schema v3</span>
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
            "Illustrative field anatomy—not a published native-admission result.",
            "仅用于展示字段结构，并非已发布的原生准入结果。",
          )}
        />
      </p>
    </figure>
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
      <div className="install-console glass" aria-label="Installation commands">
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
