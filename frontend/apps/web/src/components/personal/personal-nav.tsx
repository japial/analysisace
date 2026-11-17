"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { isActivePath } from "@/lib/nav";

/** Sections of "My money", in the order a household usually sets things up. */
export const PERSONAL_SECTIONS = [
  { key: "overview", href: "/personal" },
  { key: "costs", href: "/personal/costs" },
  { key: "portfolio", href: "/personal/portfolio" },
  { key: "assets", href: "/personal/assets" },
  { key: "sukuk", href: "/personal/sukuk" },
  { key: "performance", href: "/personal/performance" },
  { key: "allocation", href: "/personal/allocation" },
  { key: "zakat", href: "/personal/zakat" },
  { key: "tax", href: "/personal/tax" },
  { key: "fire", href: "/personal/fire" },
  { key: "goals", href: "/personal/goals" },
  { key: "alerts", href: "/personal/alerts" },
  { key: "community", href: "/personal/community" },
  { key: "household", href: "/personal/household" },
] as const;

/** Tab row for the personal finance area. Scrolls sideways on phones. */
export function PersonalNav() {
  const t = useTranslations("personal.sections");
  const pathname = usePathname();
  return (
    <div className="container" data-print="hide">
      <nav
        aria-label={t("label")}
        className="-mb-px flex gap-5 overflow-x-auto border-b border-border pt-4 [scrollbar-width:thin]"
      >
        {PERSONAL_SECTIONS.map((section) => {
          const current =
            section.href === "/personal"
              ? pathname === "/personal"
              : isActivePath(pathname, section.href);
          return (
            <Link
              key={section.key}
              href={section.href}
              aria-current={current ? "page" : undefined}
              className="inline-flex h-10 shrink-0 items-center border-b-2 border-transparent text-sm font-medium whitespace-nowrap text-secondary-foreground hover:text-mono aria-[current=page]:border-primary aria-[current=page]:text-mono"
            >
              {t(section.key)}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
