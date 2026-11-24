/**
 * Assets, Capital and Earnings over time (D23): net worth and capital at work as two lines,
 * the change over the period, and the last months' income, costs and savings. Every figure
 * comes from `/ace/trend`; this component only formats them.
 */
import type { AceTrend, Envelope } from "@analysisace/core";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { cn } from "@/lib/utils";

import { Empty, Panel } from "./display";
import { LineChart } from "./line-chart";

const TABLE_MONTHS = 6;

/** "+৳2.5 lakh" or "-৳40,000.00": the API sends the sign, this adds "+" for growth. */
function signed(text: string): string {
  return text.startsWith("-") || text === "—" ? text : `+${text}`;
}

export async function AceTrendPanel({
  trend,
  locale,
  actions,
}: {
  trend: Envelope<AceTrend>;
  locale: string;
  actions?: ReactNode;
}) {
  const t = await getTranslations("personal.overview.trend");
  const f = formatterFor(locale);
  const { months, change } = trend.data;
  const withWorth = months.filter((m) => m.net_worth !== null);
  // Without income records the API leaves income and savings empty; costs are then the
  // only column with figures, so it is shown on phones too.
  const incomeKnown = months.some((m) => m.income !== null);
  const costsColumn = incomeKnown ? "hidden sm:table-cell" : "";
  const recent = months.filter((m) => m.income !== null || m.costs !== null).slice(-TABLE_MONTHS).reverse();

  return (
    <Panel
      title={t("title")}
      description={t("intro", { n: f.num(String(months.length), 0) })}
      actions={actions}
      footnote={{ asOf: trend.as_of, sources: trend.sources }}
    >
      <div className="flex flex-col gap-6">
        {(change.net_worth !== null || change.savings_total !== null) && (
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {(
              [
                ["netWorthChange", change.net_worth],
                ["capitalChange", change.capital],
                ["savedTotal", change.savings_total],
              ] as const
            ).map(([key, value]) => (
              <div key={key} className="flex flex-col gap-0.5 rounded-xl border border-border p-3">
                <dt className="text-xs text-muted-foreground">{t(key)}</dt>
                <dd
                  className={cn(
                    "text-lg font-semibold text-mono tabular-nums",
                    value?.startsWith("-") && "text-destructive",
                  )}
                >
                  {value === null ? "—" : key === "savedTotal" ? f.compact(value) : signed(f.compact(value))}
                </dd>
              </div>
            ))}
          </dl>
        )}

        {withWorth.length < 2 ? (
          <Empty>{t("chartEmpty")}</Empty>
        ) : (
          <LineChart
            title={t("title")}
            kind="bdt"
            series={[
              { key: "net_worth", label: t("netWorth") },
              { key: "capital", label: t("capital") },
            ]}
            points={months.map((m) => ({
              label: f.month(m.month),
              values: { net_worth: m.net_worth, capital: m.capital },
            }))}
          />
        )}

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-mono">{t("tableTitle")}</h3>
          {!incomeKnown && recent.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {t("noIncome")}{" "}
              <Link href="/personal/income" className="text-primary hover:underline">
                {t("addIncome")}
              </Link>
            </p>
          )}
          {recent.length === 0 ? (
            <Empty>{t("tableEmpty")}</Empty>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("month")}</TableHead>
                    <TableHead className="text-end">{t("income")}</TableHead>
                    <TableHead className={cn("text-end", costsColumn)}>{t("costs")}</TableHead>
                    <TableHead className="text-end">{t("saved")}</TableHead>
                    <TableHead className="text-end">{t("rate")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recent.map((m) => (
                    <TableRow key={m.month}>
                      <TableCell className="whitespace-nowrap">{f.month(m.month)}</TableCell>
                      <TableCell className="text-end whitespace-nowrap tabular-nums">{f.compact(m.income)}</TableCell>
                      <TableCell className={cn("text-end whitespace-nowrap tabular-nums", costsColumn)}>{f.compact(m.costs)}</TableCell>
                      <TableCell className={cn("text-end whitespace-nowrap tabular-nums", m.savings?.startsWith("-") && "text-destructive")}>
                        {f.compact(m.savings)}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">{f.pct(m.savings_rate_pct, 0)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
