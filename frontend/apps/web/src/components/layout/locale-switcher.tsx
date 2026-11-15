"use client";

import type { Locale } from "@analysisace/i18n";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link, usePathname } from "@/i18n/navigation";

// Each language is named in its own script, so a reader can find theirs.
const NAMES: Record<Locale, string> = { bn: "বাংলা", en: "English" };

export function LocaleSwitcher() {
  const t = useTranslations("common");
  const locale = useLocale();
  const pathname = usePathname();
  const other: Locale = locale === "bn" ? "en" : "bn";

  return (
    <Button variant="ghost" asChild>
      <Link
        href={pathname}
        locale={other}
        lang={other}
        aria-label={`${t("language")}: ${NAMES[other]}`}
      >
        {NAMES[other]}
      </Link>
    </Button>
  );
}
