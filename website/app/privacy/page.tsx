import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { ISSUE_TRACKER_URL, LegalPage } from "../site";

export const metadata: Metadata = {
  title: "Privacy",
  description: "Privacy boundaries for Gloamere Workflows.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage
      route={l("Policy / Privacy", "政策 / 隐私")}
      title={l("Skills-only. No Gloamere telemetry.", "仅含 Skills，不含 Gloamere 遥测。")}
      lead={l("Last updated July 31, 2026.", "最后更新：2026 年 7 月 31 日。")}
    >
      <section>
        <h2><T value={l("What Gloamere does not collect", "Gloamere 不收集什么")} /></h2>
        <p><T value={l(
          "Gloamere Workflows is a skills-only plugin. It does not operate a Gloamere backend, create Gloamere user accounts, set Gloamere cookies, collect Gloamere telemetry, or transmit analytics to Gloamere.",
          "Gloamere Workflows 是仅包含 Skills 的插件。它不运行 Gloamere 后端、不创建 Gloamere 用户账户、不设置 Gloamere Cookie、不收集 Gloamere 遥测，也不向 Gloamere 传输分析数据。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Inputs and outputs", "输入与输出")} /></h2>
        <p><T value={l(
          "Gloamere Workflows uses only the conversation context, files, and host capabilities the user makes available. The plugin contains no UI, MCP server, background service, analytics client, or bundled connector.",
          "Gloamere Workflows 仅使用用户提供的对话上下文、文件与宿主能力。插件不包含 UI、MCP 服务器、后台服务、分析客户端或随附连接器。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Other services", "其他服务")} /></h2>
        <p><T value={l(
          "The host and any tools, connectors, websites, or services the user separately chooses to invoke are governed by their own privacy terms. Gloamere does not receive that data merely because this plugin is installed.",
          "宿主以及用户另行选择调用的工具、连接器、网站或服务，均受其各自隐私条款约束。安装本插件本身不会让 Gloamere 收到相关数据。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Questions", "问题")} /></h2>
        <p><T value={l("Raise privacy questions through the ", "请通过")} />{" "}
          <a href={ISSUE_TRACKER_URL}><T value={l("public issue tracker", "公开 Issue Tracker")} /></a>
          <T value={l(". Do not include private prompts, credentials, personal paths, or customer data.", " 提出隐私问题。请勿包含私密提示词、凭据、个人路径或客户数据。")} />
        </p>
      </section>
    </LegalPage>
  );
}
