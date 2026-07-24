import type { Metadata } from "next";
import "./globals.css";
import { I18nProvider } from "./i18n";

export const metadata: Metadata = {
  // A fixed production origin prevents private preview hosts from becoming
  // canonical URLs and also keeps the Caddy build fully static.
  metadataBase: new URL("https://codex.gloamere.com"),
  title: {
    default: "Gloamere — Evidence-led Codex plugins",
    template: "%s — Gloamere",
  },
  description:
    "Evidence-led evaluation and focused professional workflows for Codex.",
  applicationName: "Gloamere",
  authors: [{ name: "Gloamere", url: "https://gloamere.com" }],
  creator: "Gloamere",
  keywords: [
    "Codex",
    "Codex plugins",
    "Skill evaluation",
    "AI workflows",
    "Gloamere",
  ],
  icons: {
    icon: "/gloamere-icon.png",
    shortcut: "/gloamere-icon.png",
    apple: "/gloamere-icon.png",
  },
  openGraph: {
    type: "website",
    title: "Gloamere — Evidence-led Codex plugins",
    description:
      "Inspect native Skill activation and add four focused professional workflows.",
    siteName: "Gloamere",
    images: [
      {
        url: "/og-ios.png",
        width: 1728,
        height: 910,
        alt: "A frosted-glass evidence lens connecting paths to a verified Gloamere result.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Gloamere — Evidence-led Codex plugins",
    description:
      "Inspect native Skill activation and add four focused professional workflows.",
    images: ["/og-ios.png"],
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
