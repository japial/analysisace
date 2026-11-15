import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  { ignores: ["**/.next/**", "**/node_modules/**", "**/next-env.d.ts", "**/coverage/**"] },
  ...nextVitals,
  ...nextTypescript,
  { settings: { next: { rootDir: "apps/web" } } },
];

export default config;
