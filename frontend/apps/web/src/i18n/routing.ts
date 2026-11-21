import { defaultLocale, locales } from "@analysisace/i18n";
import { defineRouting } from "next-intl/routing";

// Every URL carries its language: /bn/companies, /en/companies.
export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: "always",
});
