"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { isActivePath, type NavItem } from "@/lib/nav";

/** Metronic Layout 9 menu bar under the header. Shown from the `lg` breakpoint up. */
export function SiteNavbar({ items }: { items: NavItem[] }) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <div className="hidden border-y border-border bg-muted/80 lg:block">
      <nav aria-label={t("label")} className="container flex items-stretch gap-6">
        {items.map((item) => (
          <Link
            key={item.key}
            href={item.href}
            aria-current={isActivePath(pathname, item.href) ? "page" : undefined}
            className="-mb-px inline-flex h-12 items-center border-b border-transparent text-sm font-medium text-secondary-foreground hover:text-mono aria-[current=page]:border-mono aria-[current=page]:text-mono"
          >
            {t(item.key)}
          </Link>
        ))}
      </nav>
    </div>
  );
}
