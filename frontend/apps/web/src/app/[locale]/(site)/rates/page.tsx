import type { Envelope, RatesOverview, Score } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";

import { joinSeries } from "@/components/market/chart-data";
import { MarketShell } from "@/components/market/shell";
import { Empty, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import { LineChart } from "@/components/personal/line-chart";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { loadPublic, marketSetup } from "@/lib/market";
import { seriesLabel } from "@/lib/market-labels";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "market.rates" });
  return { title: t("metaTitle"), description: t("intro") };
}

async function ScoreTable({ rows, link }: { rows: Score[]; link: boolean }) {
  const t = await getTranslations();
  const f = formatterFor(await getLocale());
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("market.rates.subject")}</TableHead>
          <TableHead className="text-end">{t("market.rates.score")}</TableHead>
          <TableHead>{t("market.rates.confidence")}</TableHead>
          <TableHead className="hidden text-end sm:table-cell">{t("market.rates.weeks")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.subject}>
            <TableCell>
              {link ? (
                <Link href={`/companies/${row.subject}`} lang="en" className="font-medium text-primary hover:underline">
                  {row.subject}
                </Link>
              ) : (
                <span className="text-mono">{row.subject}</span>
              )}
            </TableCell>
            <TableCell className="text-end tabular-nums">{f.pct(row.value, 2, true)}</TableCell>
            <TableCell>
              <Badge variant="secondary" appearance="light" size="sm">
                {t(`market.scores.confidence.${row.confidence}`)}
              </Badge>
            </TableCell>
            <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.num(String(row.n_obs), 0)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** F3: auction yields and trend (FR3.5) beside sector and stock scores. */
export default async function RatesPage({ params }: Props) {
  const { locale } = await params;
  const { t, f } = await marketSetup(locale);
  const [overview, stocks] = await Promise.all([
    loadPublic<Envelope<RatesOverview>>("/rates/overview"),
    loadPublic<Envelope<Score[]>>("/scores?subject_type=TICKER&score_type=RATE_SENSITIVITY"),
  ]);
  const sectors = overview.ok ? overview.data.data.sectors.filter((s) => s.score_type === "RATE_SENSITIVITY") : [];

  return (
    <MarketShell title={t("market.rates.title")} description={t("market.rates.intro")}>
      {!overview.ok ? (
        <LoadError code={overview.code} />
      ) : (
        <>
          <Panel
            title={t("market.rates.auctions")}
            footnote={{ asOf: overview.data.as_of, sources: overview.data.sources }}
          >
            {overview.data.data.latest_auctions.length === 0 ? (
              <Empty>{t("market.scores.none")}</Empty>
            ) : (
              <div className="flex flex-col gap-5">
                <StatGrid>
                  {overview.data.data.latest_auctions.map((a) => (
                    <Stat key={a.code} label={seriesLabel(t, a.code)} value={f.pct(a.value)} hint={f.date(a.date)} />
                  ))}
                </StatGrid>
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-mono">{t("market.rates.trend")}</h3>
                  <LineChart
                    title={t("market.rates.trend")}
                    kind="index"
                    series={[{ key: "TBILL_91D", label: seriesLabel(t, "TBILL_91D") }]}
                    points={joinSeries({ TBILL_91D: overview.data.data.yield_trend }, (d) => f.date(d))}
                  />
                </div>
              </div>
            )}
          </Panel>

          <Panel title={t("market.rates.sectorsTitle")} description={t("market.scores.intro")} table={sectors.length > 0}>
            {sectors.length === 0 ? <Empty>{t("market.scores.none")}</Empty> : <ScoreTable rows={sectors} link={false} />}
          </Panel>
        </>
      )}

      <Panel
        title={t("market.rates.stocksTitle")}
        table={stocks.ok && stocks.data.data.length > 0}
        footnote={stocks.ok ? { asOf: stocks.data.as_of, sources: stocks.data.sources } : undefined}
      >
        {!stocks.ok ? (
          <LoadError code={stocks.code} />
        ) : stocks.data.data.length === 0 ? (
          <Empty>{t("market.scores.none")}</Empty>
        ) : (
          <ScoreTable rows={stocks.data.data} link />
        )}
      </Panel>
    </MarketShell>
  );
}
