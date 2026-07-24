import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { LegalPage, SECURITY_REPORT_URL } from "../site";

export const metadata: Metadata = {
  title: "Security",
  description:
    "Supported versions, private vulnerability reporting, and security boundaries for Gloamere.",
  alternates: { canonical: "/security" },
};

export default function SecurityPage() {
  return (
    <LegalPage
      route={l("Policy / Security", "政策 / 安全")}
      title={l("Verify the release. Report vulnerabilities privately.", "验证发行版，私下报告漏洞。")}
      lead={l(
        "Before the beta tag exists, reports target the release candidate; afterward, fixes target the latest published Gloamere 4.x tag.",
        "Beta 标签发布前，报告针对候选版；发布后，修复目标为最新发布的 Gloamere 4.x 标签。",
      )}
    >
      <section>
        <h2><T value={l("Supported versions", "支持版本")} /></h2>
        <p><T value={l(
          "Historical 3.x artifacts are retained for traceability, but they are not an active compatibility or security-support surface.",
          "历史 3.x 产物会为可追溯性保留，但不属于当前兼容性或安全支持范围。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Report a vulnerability", "报告漏洞")} /></h2>
        <p><T value={l("Use ", "请使用 ")} />
          <a href={SECURITY_REPORT_URL}><T value={l("GitHub private vulnerability reporting", "GitHub 私密漏洞报告")} /></a>
          <T value={l(". Do not open a public issue for a suspected vulnerability.", "。请勿为疑似漏洞创建公开 Issue。")} />
        </p>
        <p><T value={l(
          "Include the affected plugin and version, Codex, Python, and operating system versions, impact, reproduction steps, and a minimal proof of concept. Remove API keys, tokens, private prompts, personal paths, and customer data.",
          "请包含受影响插件与版本、Codex、Python 和操作系统版本、影响、复现步骤与最小概念验证。移除 API Key、Token、私密提示词、个人路径与客户数据。",
        )} /></p>
        <p><T value={l(
          "Gloamere will acknowledge the report through GitHub and coordinate disclosure after a fix is available. The beta does not promise a fixed response-time SLA.",
          "Gloamere 会通过 GitHub 确认报告，并在修复可用后协调披露。Beta 阶段不承诺固定响应时间 SLA。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Security boundary", "安全边界")} /></h2>
        <ul>
          <li><T value={l("The prepared plugins contain no Gloamere backend, telemetry, hooks, MCP servers, or background services.", "当前插件不包含 Gloamere 后端、遥测、Hook、MCP 服务器或后台服务。")} /></li>
          <li><T value={l("Plugins still operate within the permissions and tools granted to Codex; users should review requested actions and protect local inputs.", "插件仍在授予 Codex 的权限与工具范围内运行；用户应审阅请求的操作并保护本地输入。")} /></li>
          <li><T value={l("Install immutable tagged releases and compare archives against their published SHA-256 sidecars.", "安装不可变的标签发行版，并使用已发布 SHA-256 校验文件比对归档。")} /></li>
          <li><T value={l("Missing, malformed, truncated, or unknown Eval evidence is non-verified. A model statement is not proof that a Skill was loaded.", "缺失、畸形、截断或未知的 Eval 证据均为非 verified；模型声明不能证明 Skill 已加载。")} /></li>
        </ul>
      </section>
    </LegalPage>
  );
}
