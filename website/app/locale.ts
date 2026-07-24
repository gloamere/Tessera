export type Locale = "en" | "zh-CN";
export type LocalizedText = { en: string; zh: string };

export const l = (en: string, zh: string): LocalizedText => ({ en, zh });

export function localize(value: LocalizedText, locale: Locale) {
  return locale === "zh-CN" ? value.zh : value.en;
}
