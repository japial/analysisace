/**
 * Assets, Capital and Earnings at a glance (D19). Figures come from `/ace/summary`; this
 * component only formats them.
 */
import type { AceSummary, Envelope } from "@analysisace/core";
import { PiggyBank, Scale, TrendingUp, type LucideIcon } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";

import { Panel } from "./display";

export async function AceSummaryPanel({ summary, locale }: { summary: Envelope<AceSummary>; locale: string }) {
  const t = await getTranslations("personal.overview.ace");
  const f = formatterFor(locale);
  const { assets, capital, earnings } = summary.data;

  const pillars: {
    key: "assets" | "capital" | "earnings";
    icon: LucideIcon;
    href: string;
    value: string;
    hint: string;
    note?: string;
  }[] = [
    {
      key: "assets",
      icon: Scale,
      href: "/personal/assets",
      value: f.compact(assets.net_worth),
      hint: t("assetsHint", { assets: f.compact(assets.total), debts: f.compact(assets.liabilities) }),
    },
    {
      key: "capital",
      icon: TrendingUp,
      href: "/personal/portfolio",
      value: f.compact(capital.at_work),
      hint:
        capital.share_of_assets_pct === null
          ? t("capitalEmpty")
          : t("capitalHint", { pct: f.pct(capital.share_of_assets_pct, 0) }),
    },
    {
      key: "earnings",
      icon: PiggyBank,
      href: "/personal/income",
      value: earnings.average_monthly_savings === null ? "—" : f.compact(earnings.average_monthly_savings),
      hint:
        earnings.average_monthly_savings === null
          ? t("earningsEmpty")
          : earnings.savings_rate_pct === null
            ? t("earningsHint", { n: f.num(String(earnings.months_counted), 0) })
            : t("earningsRateHint", {
                rate: f.pct(earnings.savings_rate_pct, 0),
                n: f.num(String(earnings.months_counted), 0),
              }),
      note:
        earnings.average_monthly_income === null
          ? t("incomeNote")
          : t("incomeCosts", {
              income: f.compact(earnings.average_monthly_income),
              costs: earnings.average_monthly_cost === null ? "—" : f.compact(earnings.average_monthly_cost),
            }),
    },
  ];

  return (
    <Panel
      title={t("title")}
      description={t("intro")}
      footnote={{ asOf: summary.as_of, sources: summary.sources }}
    >
      <ul className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {pillars.map(({ key, icon: Icon, href, value, hint, note }) => (
          <li key={key}>
            <Link
              href={href}
              className="flex h-full flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <span className="flex items-center gap-2 text-sm font-medium text-primary">
                <Icon className="size-4" aria-hidden="true" />
                {t(`${key}.title`)}
              </span>
              <span className="text-sm text-muted-foreground">{t(`${key}.label`)}</span>
              <span className="text-2xl font-semibold text-mono tabular-nums">{value}</span>
              <span className="text-xs text-muted-foreground">{hint}</span>
              {note && <span className="mt-1 text-xs text-muted-foreground">{note}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
