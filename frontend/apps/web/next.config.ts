import path from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // Workspace packages ship TypeScript source.
  transpilePackages: ["@analysisace/core", "@analysisace/i18n"],
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
};

export default withNextIntl(nextConfig);
