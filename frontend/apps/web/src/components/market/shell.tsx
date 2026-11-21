/**
 * Frame for the public market pages (F1 to F8): toolbar, content and the required
 * disclaimer (PRD section 0).
 */
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { Toolbar } from "@/components/layout/toolbar";

interface Props {
  title: string;
  description?: string;
  /** Crumbs between "Home" and this page. */
  trail?: { label: string; href?: string }[];
  actions?: ReactNode;
  children: ReactNode;
}

export async function MarketShell({ title, description, trail = [], actions, children }: Props) {
  const t = await getTranslations("nav");
  return (
    <>
      <Toolbar
        title={title}
        description={description}
        breadcrumbs={[{ label: t("home"), href: "/" }, ...trail, { label: title }]}
      >
        {actions}
      </Toolbar>
      <div className="container flex flex-col gap-5 pb-10 lg:gap-7.5">
        <Disclaimer />
        {children}
      </div>
    </>
  );
}

/** A signed percentage, neutral in colour: moves are described, never judged. */
export function Pct({ value, text }: { value: string | null | undefined; text: string }) {
  if (value === null || value === undefined) return <span className="text-muted-foreground">—</span>;
  return <span className="tabular-nums text-mono">{text}</span>;
}
