import { releaseData } from "./generated-release";
import { l } from "./locale";

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
    default:
      return l("Directory status pending", "目录状态待定");
  }
})();
