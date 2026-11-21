import type { Envelope, Regime } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MarketShell } from "@/components/market/shell";
import { Empty, Facts, LoadError, Panel } from "@/components/personal/display";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { loadPublic, marketSetup } from "@/lib/market";
import { regimeLabel } from "@/lib/market-labels";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "market.regime" });
  return { title: t("metaTitle"), description: t("intro") };
}

/** F8: the current rules-based regime (FR8.1) and sectors in past months like it (FR8.2). */
export default async function RegimePage({ params }: Props) {
  const { locale } = await params;
  const { t, f } = await marketSetup(locale);
  const result = await loadPublic<Envelope<Regime>>("/regime?months=24");

  return (
    <MarketShell title={t("market.regime.title")} description={t("market.regime.intro")}>
      <Alert variant="info" appearance="light">
        <AlertDescription>{t("market.regime.provisional")}</AlertDescription>
      </Alert>
      {!result.ok ? (
        <LoadError code={result.code} />
      ) : !result.data.data.current ? (
        <Panel title={t("market.regime.current")}>
          <Empty>{t("market.regime.none")}</Empty>
        </Panel>
      ) : (
        <>
          <Panel
            title={t("market.regime.current")}
            description={f.month(result.data.data.current.month)}
            footnote={{ asOf: result.data.as_of, sources: result.data.sources }}
          >
            <div className="flex flex-col gap-5">
              <p className="text-xl font-semibold text-mono">{regimeLabel(t, result.data.data.current.label)}</p>
              <Facts
                items={[
                  {
                    label: t("market.regime.yieldChange"),
                    value: result.data.data.current.components.yield_change_pts
                      ? t("market.regime.pts", { value: f.num(result.data.data.current.components.yield_change_pts) })
                      : "—",
                  },
                  { label: t("market.regime.cpi"), value: f.pct(result.data.data.current.components.cpi_yoy) },
                  { label: t("market.regime.oilChange"), value: f.pct(result.data.data.current.components.oil_change_pct, 2, true) },
                ]}
              />
            </div>
          </Panel>

          <Panel
            title={t("market.regime.sectorsTitle")}
            description={t("market.regime.sectorsIntro")}
            table={result.data.data.sectors.length > 0}
          >
            {result.data.data.sectors.length === 0 ? (
              <Empty>{t("market.regime.noSectors")}</Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("market.regime.sector")}</TableHead>
                    <TableHead className="text-end">{t("market.regime.avgReturn")}</TableHead>
                    <TableHead className="text-end">{t("market.regime.hitRate")}</TableHead>
                    <TableHead className="text-end">{t("market.regime.months")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.data.data.sectors.map((s) => (
                    <TableRow key={s.sector}>
                      <TableCell>{s.sector}</TableCell>
                      <TableCell className="text-end tabular-nums">{f.pct(s.avg_monthly_return, 2, true)}</TableCell>
                      <TableCell className="text-end tabular-nums">{f.pct(s.hit_rate, 0)}</TableCell>
                      <TableCell className="text-end tabular-nums">
                        {f.num(String(s.n_months), 0)}
                        {s.n_months < result.data.data.min_months && (
                          <Badge variant="warning" appearance="light" size="sm" className="ms-2">
                            {t("market.regime.tooFew")}
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Panel>

          <Panel title={t("market.regime.history")} table>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("market.regime.month")}</TableHead>
                  <TableHead>{t("market.regime.label")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.data.data.history.map((m) => (
                  <TableRow key={m.month}>
                    <TableCell className="tabular-nums">{f.month(m.month)}</TableCell>
                    <TableCell className="text-secondary-foreground">{regimeLabel(t, m.label)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Panel>
        </>
      )}
    </MarketShell>
  );
}
