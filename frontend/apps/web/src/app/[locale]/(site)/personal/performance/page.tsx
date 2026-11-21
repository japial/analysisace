import type { Envelope, Performance } from "@analysisace/core";

import { Empty, Facts, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import { LineChart } from "@/components/personal/line-chart";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import { type PageProps, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("performance");

const PERIODS = ["1Y", "3Y", "5Y", "ALL"] as const;

interface Props extends PageProps {
  searchParams: Promise<{ period?: string }>;
}

/** Past returns, risk and benchmarks (F15). Describes what happened; it does not predict. */
export default async function PerformancePage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/performance");
  const title = t("personal.sections.performance");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const requested = (await searchParams).period;
  const period = PERIODS.find((p) => p === requested) ?? "ALL";
  const result = await load(hh<Envelope<Performance>>(ctx, `/portfolio/performance?period=${period}`));

  return (
    <PersonalShell
      ctx={ctx}
      title={title}
      description={t("personal.performance.intro")}
      actions={
        <div className="flex gap-1" role="group" aria-label={t("personal.performance.period")}>
          {PERIODS.map((p) => (
            <Button key={p} variant={p === period ? "primary" : "outline"} size="sm" asChild>
              <Link href={{ pathname: "/personal/performance", query: { period: p } }} aria-current={p === period ? "true" : undefined}>
                {t(`personal.performance.periods.${p}`)}
              </Link>
            </Button>
          ))}
        </div>
      }
    >
      {!result.ok ? (
        <LoadError code={result.code} />
      ) : (
        <PerformanceBody data={result.data} />
      )}
    </PersonalShell>
  );

  function PerformanceBody({ data: envelope }: { data: Envelope<Performance> }) {
    const d = envelope.data;
    const footnote = { asOf: envelope.as_of, sources: envelope.sources };
    const benchmarkCodes = d.benchmarks.map((b) => b.code);
    return (
      <>
        <p className="text-sm text-muted-foreground">
          {t("personal.performance.window", { start: f.date(d.start), end: f.date(d.end) })}
        </p>
        <StatGrid>
          <Stat label={t("personal.performance.twr")} value={f.pct(d.twr_pct, 2, true)} hint={t("personal.performance.twrHint")} />
          <Stat label={t("personal.performance.twrAnnual")} value={f.pct(d.twr_annualised_pct, 2, true)} />
          <Stat label={t("personal.performance.xirr")} value={f.pct(d.xirr_pct, 2, true)} hint={t("personal.performance.xirrHint")} />
          <Stat label={t("personal.performance.value")} value={f.compact(d.value)} hint={f.bdt(d.value)} />
          <Stat label={t("personal.performance.volatility")} value={f.pct(d.volatility_pct)} hint={t("personal.performance.volatilityHint")} />
          <Stat label={t("personal.performance.drawdown")} value={f.pct(d.max_drawdown_pct)} hint={t("personal.performance.drawdownHint")} tone="negative" />
          <Stat
            label={t("personal.performance.riskFree")}
            value={f.pct(d.risk_free_pct)}
            hint={t("personal.performance.riskFreeHint")}
          />
        </StatGrid>

        <Panel title={t("personal.performance.chartTitle")} description={t("personal.performance.chartIntro")} footnote={footnote}>
          {d.chart.length < 2 ? (
            <Empty>{t("personal.performance.noChart")}</Empty>
          ) : (
            <LineChart
              title={t("personal.performance.chartTitle")}
              kind="index"
              series={[
                { key: "portfolio", label: t("personal.performance.yourPortfolio") },
                ...benchmarkCodes.map((code) => ({ key: code, label: code })),
              ]}
              points={d.chart.map((p) => ({
                label: f.date(p.date),
                values: Object.fromEntries(
                  ["portfolio", ...benchmarkCodes].map((key) => [key, p[key] ?? null]),
                ),
              }))}
            />
          )}
        </Panel>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
          <Panel title={t("personal.performance.benchmarks")} table>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.performance.index")}</TableHead>
                  <TableHead className="text-end">{t("personal.performance.return")}</TableHead>
                  <TableHead className="text-end">{t("personal.performance.annualised")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium text-mono">{t("personal.performance.yourPortfolio")}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(d.twr_pct, 2, true)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(d.twr_annualised_pct, 2, true)}</TableCell>
                </TableRow>
                {d.benchmarks.map((b) => (
                  <TableRow key={b.code}>
                    <TableCell lang="en">{b.code}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.pct(b.return_pct, 2, true)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.pct(b.annualised_pct, 2, true)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Panel>

          <Panel title={t("personal.performance.diversification")}>
            {d.diversification ? (
              <Facts
                items={[
                  { label: t("personal.performance.holdingsCount"), value: f.num(d.diversification.holdings, 0) },
                  {
                    label: t("personal.performance.topWeight", { n: f.num(d.diversification.top_n, 0) }),
                    value: f.pct(d.diversification.top_weight_pct),
                  },
                  { label: t("personal.performance.sectors"), value: f.num(d.diversification.sectors, 0) },
                  { label: t("personal.performance.herfindahl"), value: f.num(d.diversification.sector_herfindahl, 4) },
                ]}
              />
            ) : (
              <Empty>{t("personal.performance.noChart")}</Empty>
            )}
          </Panel>
        </div>

        <Panel title={t("personal.performance.byAccount")} table footnote={footnote}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.portfolio.account")}</TableHead>
                <TableHead className="text-end">{t("personal.performance.twrAnnual")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("personal.performance.xirr")}</TableHead>
                <TableHead className="text-end">{t("personal.performance.value")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.accounts.map((a) => (
                <TableRow key={a.account_id}>
                  <TableCell>{a.institution}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(a.twr_annualised_pct, 2, true)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(a.xirr_pct, 2, true)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(a.value)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      </>
    );
  }
}
