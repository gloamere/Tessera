import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { ISSUE_TRACKER_URL, LegalPage } from "../site";

export const metadata: Metadata = {
  title: "Privacy",
  description: "Privacy boundaries for Gloamere Eval and Gloamere Workflows.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage
      route={l("Policy / Privacy", "政策 / 隐私")}
      title={l("Local plugins. No Gloamere telemetry.", "本地插件，不含 Gloamere 遥测。")}
      lead={l("Last updated July 23, 2026.", "最后更新：2026 年 7 月 23 日。")}
    >
      <section>
        <h2><T value={l("What Gloamere does not collect", "Gloamere 不收集什么")} /></h2>
        <p><T value={l(
          "Gloamere Eval and Gloamere Workflows are local, skill-based Codex plugins. They do not operate a Gloamere backend, create user accounts, set cookies, collect telemetry, or transmit analytics to Gloamere.",
          "Gloamere Eval 与 Gloamere Workflows 是基于 Skill 的本地 Codex 插件。它们不运行 Gloamere 后端、不创建用户账户、不设置 Cookie、不收集遥测，也不向 Gloamere 传输分析数据。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Local inputs and outputs", "本地输入与输出")} /></h2>
        <p><T value={l("Gloamere Eval reads the case files and project context selected by the user. It writes JSON to stdout by default and creates a report file only when the user explicitly supplies ", "Gloamere Eval 读取用户选择的案例文件与项目上下文。默认将 JSON 写入 stdout，只有用户显式提供 ")} /><code>--output</code><T value={l(".", " 时才创建报告文件。")} /></p>
        <p><T value={l(
          "Gloamere Workflows use the project files and Codex capabilities authorized by the user. Bundled helper scripts operate locally.",
          "Gloamere Workflows 使用用户授权的项目文件与 Codex 能力，随附辅助脚本在本地运行。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Other services", "其他服务")} /></h2>
        <p><T value={l(
          "Codex and any tools, connectors, websites, or services the user separately chooses to invoke are governed by their own privacy terms. Gloamere does not receive that data merely because one of these plugins is installed.",
          "Codex 以及用户另行选择调用的工具、连接器、网站或服务，均受其各自隐私条款约束。安装这些插件本身不会让 Gloamere 收到相关数据。",
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
