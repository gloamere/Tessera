import { releaseData } from "./generated-release";
import { l } from "./locale";

export const RELEASE_STATUS_VALUE: string = releaseData.releaseStatus;
export const RELEASE_PUBLISHED = RELEASE_STATUS_VALUE === "published";
export const MARKETPLACE_STATUS = RELEASE_PUBLISHED
  ? l("Available from the tagged Git marketplace", "已通过带标签的 Git marketplace 发布")
  : l("Git marketplace release candidate", "Git marketplace 发布候选版");

export const DIRECTORY_STATUS_VALUE: string = releaseData.directoryStatus;
export const DIRECTORY_URL: string | null = releaseData.directoryURL;
export const DIRECTORY_APPROVED =
  DIRECTORY_STATUS_VALUE === "approved" && DIRECTORY_URL !== null;

export const DIRECTORY_STATUS = (() => {
  switch (DIRECTORY_STATUS_VALUE) {
    case "preparing":
      return l("Preparing for directory review", "官方目录审核准备中");
    case "submitted":
      return l("Directory review in progress", "官方目录审核中");
    case "approved":
      return l("Available in the official directory", "已在官方目录上线");
    case "optional":
      return l("Official directory is a future option", "官方目录为未来可选项");
    default:
      return l("Directory status pending", "目录状态待定");
  }
})();
