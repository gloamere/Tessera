import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { RELEASE_PUBLISHED } from "../release-state";
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
      title={l("Verify the tag. Report vulnerabilities privately.", "验证发布标签，私下报告漏洞。")}
      lead={RELEASE_PUBLISHED
        ? l(
            "Reports and fixes target the latest tagged Gloamere Workflows version.",
            "报告与修复目标为最新带标签的 Gloamere Workflows 版本。",
          )
        : l(
            "Before v4.0.0 is tagged, reports target the local release candidate; afterward, fixes target the latest published Gloamere Workflows version.",
            "v4.0.0 打标签前，报告针对本地发布候选版；发布后，修复目标为最新的 Gloamere Workflows 版本。",
          )}
    >
      <section>
        <h2><T value={l("Supported versions", "支持版本")} /></h2>
        <p><T value={RELEASE_PUBLISHED
          ? l(
              "The latest tagged Git marketplace release is the active compatibility and security-support surface. Historical releases remain visible for traceability.",
              "最新带标签的 Git marketplace 发布版是当前兼容性与安全支持范围。历史版本会为可追溯性保留。",
            )
          : l(
              "The v4.0.0 tag is not yet available. Historical repository releases remain visible for traceability but are not an active compatibility or security-support surface.",
              "v4.0.0 标签尚未发布。历史仓库版本会为可追溯性保留，但不属于当前兼容性或安全支持范围。",
            )} /></p>
      </section>
      <section>
        <h2><T value={l("Report a vulnerability", "报告漏洞")} /></h2>
        <p><T value={l("Use ", "请使用 ")} />
          <a href={SECURITY_REPORT_URL}><T value={l("GitHub private vulnerability reporting", "GitHub 私密漏洞报告")} /></a>
          <T value={l(". Do not open a public issue for a suspected vulnerability.", "。请勿为疑似漏洞创建公开 Issue。")} />
        </p>
        <p><T value={l(
          "Include the affected plugin version, host surface and version, impact, reproduction steps, and a minimal proof of concept. Remove API keys, tokens, private prompts, personal paths, and customer data.",
          "请包含受影响的插件版本、宿主端与版本、影响、复现步骤与最小概念验证。移除 API Key、Token、私密提示词、个人路径与客户数据。",
        )} /></p>
        <p><T value={l(
          RELEASE_PUBLISHED
            ? "Gloamere will acknowledge the report through GitHub and coordinate disclosure after a fix is available. No fixed response-time SLA is promised."
            : "Gloamere will acknowledge the report through GitHub and coordinate disclosure after a fix is available. The release candidate does not promise a fixed response-time SLA.",
          RELEASE_PUBLISHED
            ? "Gloamere 会通过 GitHub 确认报告，并在修复可用后协调披露；不承诺固定响应时间 SLA。"
            : "Gloamere 会通过 GitHub 确认报告，并在修复可用后协调披露。发布候选阶段不承诺固定响应时间 SLA。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Security boundary", "安全边界")} /></h2>
        <ul>
          <li><T value={l("The release candidate contains no Gloamere backend, telemetry, hooks, plugin UI, MCP server, or background service.", "发布候选版不包含 Gloamere 后端、遥测、Hook、插件 UI、MCP 服务器或后台服务。")} /></li>
          <li><T value={l("The Skills still operate within permissions and tools granted by the host; users should review requested actions and protect inputs.", "这些 Skill 仍在宿主授予的权限与工具范围内运行；用户应审阅请求的操作并保护输入。")} /></li>
          <li><T value={l("After release, install only from the verified immutable repository tag.", "发布后，仅从经过验证的不可变仓库标签安装。")} /></li>
          <li><T value={l("Workflow output may be incomplete or incorrect and must be reviewed before it drives a product decision or repository change.", "工作流输出可能不完整或不正确，在用于产品决策或仓库变更前必须审阅。")} /></li>
        </ul>
      </section>
    </LegalPage>
  );
}
