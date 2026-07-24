import type { Metadata } from "next";
import { T } from "../i18n";
import { l } from "../locale";
import { ISSUE_TRACKER_URL, LegalPage, REPOSITORY_URL } from "../site";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms of use for Gloamere Codex plugins.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalPage
      route={l("Policy / Terms", "政策 / 条款")}
      title={l("Open source, used with review.", "开源，但请审慎使用。")}
      lead={l("Last updated July 23, 2026.", "最后更新：2026 年 7 月 23 日。")}
    >
      <section>
        <h2><T value={l("License and warranty", "许可证与保证")} /></h2>
        <p><T value={l("Gloamere Eval and Gloamere Workflows are provided under the repository’s ", "Gloamere Eval 与 Gloamere Workflows 依据仓库的 ")} />
          <a href={`${REPOSITORY_URL}/blob/main/LICENSE`}>MIT License</a>
          <T value={l(". They are provided “as is,” without warranties or a guarantee that generated analysis, recommendations, or reports are complete or correct.", " 提供。软件按“原样”提供，不作任何保证，也不保证生成的分析、建议或报告完整或正确。")} />
        </p>
      </section>
      <section>
        <h2><T value={l("User responsibility", "用户责任")} /></h2>
        <p><T value={l(
          "Users remain responsible for reviewing plugin output, protecting confidential data, respecting third-party rights, and approving any action performed through Codex or another tool.",
          "用户仍有责任审阅插件输出、保护机密数据、尊重第三方权利，并批准通过 Codex 或其他工具执行的任何操作。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Professional advice", "专业建议")} /></h2>
        <p><T value={l(
          "The workflows do not replace professional legal, financial, tax, security, medical, or compliance advice.",
          "这些工作流不能替代专业的法律、财务、税务、安全、医疗或合规建议。",
        )} /></p>
      </section>
      <section>
        <h2><T value={l("Acceptance and questions", "接受与问题")} /></h2>
        <p><T value={l("By using a plugin, the user agrees to the license and these terms. Questions may be raised through the ", "使用插件即表示用户同意许可证与本条款。问题可通过")} />{" "}
          <a href={ISSUE_TRACKER_URL}><T value={l("public issue tracker", "公开 Issue Tracker")} /></a>
          <T value={l(".", " 提出。")} />
        </p>
      </section>
    </LegalPage>
  );
}
