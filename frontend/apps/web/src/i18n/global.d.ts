import type { Locale, Messages } from "@analysisace/i18n";

// Makes message keys and the locale type-checked in useTranslations and getTranslations.
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: Messages;
  }
}
