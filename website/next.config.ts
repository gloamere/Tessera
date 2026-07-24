import type { NextConfig } from "next";

const staticExport = process.env.GLOAMERE_STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? {
      // Caddy serves the exported route directories directly; the default
      // build remains the Worker bundle used by the private Sites preview.
      output: "export",
      trailingSlash: true,
      images: {
        unoptimized: true,
      },
    }
  : {};

export default nextConfig;
