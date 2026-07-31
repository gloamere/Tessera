import type { Metadata } from "next";
import "@fontsource/playfair-display/500.css";
import "@fontsource/playfair-display/500-italic.css";
import "@fontsource/playfair-display/600.css";
import "@fontsource/ibm-plex-sans-condensed/400.css";
import "@fontsource/ibm-plex-sans-condensed/500.css";
import "@fontsource/ibm-plex-sans-condensed/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import { I18nProvider } from "./i18n";

export const metadata: Metadata = {
  // A fixed production origin prevents private preview hosts from becoming
  // canonical URLs and also keeps the Caddy build fully static.
  metadataBase: new URL("https://codex.gloamere.com"),
  title: {
    default: "Gloamere — Evidence-backed product workflows",
    template: "%s — Gloamere",
  },
  description:
    "Evidence-backed workflows for product decisions, visual reviews, and durable knowledge.",
  applicationName: "Gloamere",
  authors: [{ name: "Gloamere", url: "https://gloamere.com" }],
  creator: "Gloamere",
  keywords: [
    "product decisions",
    "visual review",
    "knowledge capture",
    "AI product workflows",
    "Gloamere",
  ],
  icons: {
    icon: "/gloamere-icon.png",
    shortcut: "/gloamere-icon.png",
    apple: "/gloamere-icon.png",
  },
  openGraph: {
    type: "website",
    title: "Gloamere — Evidence-backed product workflows",
    description:
      "Decide what to build, review what is visible, and preserve what the team learned.",
    siteName: "Gloamere",
  },
  twitter: {
    card: "summary",
    title: "Gloamere — Evidence-backed product workflows",
    description:
      "Decide what to build, review what is visible, and preserve what the team learned.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
