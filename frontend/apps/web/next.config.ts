import path from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // A separate output folder for test builds (NEXT_DIST_DIR=.next-verify), so a production
  // build never replaces the files a running dev server is serving from `.next`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Workspace packages ship TypeScript source.
  transpilePackages: ["@analysisace/core", "@analysisace/i18n"],
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  experimental: {
    // Documents for alternative investments go through a server action. The API accepts up
    // to 5 MB (config/personal.yaml, documents.max_bytes); base64 and form fields add the rest.
    serverActions: { bodySizeLimit: "8mb" },
  },
};

export default withNextIntl(nextConfig);
