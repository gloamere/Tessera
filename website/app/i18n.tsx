"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  localize,
  type Locale,
  type LocalizedText,
} from "./locale";

export type { Locale, LocalizedText } from "./locale";

const STORAGE_KEY = "gloamere-locale";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>("en");
  const hydrated = useRef(false);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const next =
      saved === "en" || saved === "zh-CN"
        ? saved
        : navigator.language.toLowerCase().startsWith("zh")
          ? "zh-CN"
          : "en";
    document.documentElement.lang = next;
    document.documentElement.dataset.locale = next;
    // 首屏保持服务端英文快照稳定，挂载后再应用浏览器偏好，避免 hydration 内容漂移。
    const timer = window.setTimeout(() => {
      hydrated.current = true;
      setLocale(next);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    document.documentElement.lang = locale;
    document.documentElement.dataset.locale = locale;
    window.localStorage.setItem(STORAGE_KEY, locale);
  }, [locale]);

  const value = useMemo(() => ({ locale, setLocale }), [locale]);

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useLocale must be used inside I18nProvider");
  }
  return value;
}

export function T({ value }: { value: LocalizedText }) {
  const { locale } = useLocale();
  return <>{localize(value, locale)}</>;
}

export function LanguageSwitch() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="language-switch" aria-label="Language / 语言">
      <button
        type="button"
        aria-pressed={locale === "zh-CN"}
        onClick={() => setLocale("zh-CN")}
      >
        中
      </button>
      <button
        type="button"
        aria-pressed={locale === "en"}
        onClick={() => setLocale("en")}
      >
        EN
      </button>
    </div>
  );
}
