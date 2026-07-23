import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const rawHost =
    requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const rawProtocol = requestHeaders.get("x-forwarded-proto");
  const host = rawHost?.split(",")[0]?.trim() || "localhost";
  const forwardedProtocol = rawProtocol?.split(",")[0]?.trim();
  const protocol =
    forwardedProtocol === "http" ||
    (!forwardedProtocol && /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(host))
      ? "http"
      : "https";

  let metadataBase: URL;
  try {
    metadataBase = new URL(`${protocol}://${host}`);
  } catch {
    // Malformed proxy headers should not break page rendering.
    metadataBase = new URL("https://localhost");
  }

  return {
    metadataBase,
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
          url: "/og.png",
          width: 1728,
          height: 910,
          alt: "An evidence trail connecting Codex evaluation stages to the Gloamere mark.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Gloamere — Evidence-led Codex plugins",
      description:
        "Inspect native Skill activation and add four focused professional workflows.",
      images: ["/og.png"],
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
