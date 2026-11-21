import type { Envelope, MarketCheck } from "@analysisace/core";

import { Empty, LoadError, Panel, ShareBars, ShariahBadge, Stat, StatGrid } from "@/components/personal/display";
import { PersonalShell } from "@/components/personal/shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { pick } from "@/lib/market";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("marketCheck");

/** F6: listed holdings against the Shariah screen, rate scores and past shocks. */
export default async function MarketCheckPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/market-check");
  const title = t("personal.sections.marketCheck");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const result = await load(hh<Envelope<MarketCheck>>(ctx, "/portfolio/market-check"));
  if (!result.ok) {
    return (
      <PersonalShell ctx={ctx} title={title}>
        <LoadError code={result.code} />
      </PersonalShell>
    );
  }
  const d = result.data.data;
  const footnote = { asOf: result.data.as_of, sources: result.data.sources };
  if (d.holdings.length === 0) {
    return (
      <PersonalShell ctx={ctx} title={title} description={t("personal.marketCheck.intro")}>
        <Panel title={t("personal.marketCheck.holdingsTitle")}>
          <Empty>{t("personal.marketCheck.empty")}</Empty>
        </Panel>
      </PersonalShell>
    );
  }

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.marketCheck.intro")}>
      <StatGrid>
        <Stat label={t("personal.marketCheck.listedValue")} value={f.bdt(d.listed_value)} hint={f.date(d.as_of_day)} />
        <Stat
          label={t("personal.marketCheck.rateWeighted")}
          value={f.pct(d.rate_sensitivity.weighted_pct, 2, true)}
          hint={t("personal.marketCheck.coverage", { pct: f.pct(d.rate_sensitivity.coverage_pct, 0) })}
        />
        <Stat
          label={t("personal.marketCheck.total")}
          value={f.bdt(d.purification.total)}
          hint={
            d.purification.dividends_unknown_ratio !== "0.00"
              ? t("personal.marketCheck.unknownRatio", { amount: f.bdt(d.purification.dividends_unknown_ratio) })
              : undefined
          }
        />
      </StatGrid>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.marketCheck.shariahTitle")} footnote={footnote}>
          <ShareBars
            rows={d.shariah_share.map((row) => ({
              key: row.status,
              label: enumLabel(t, "shariah", row.status),
              value: "",
              pct: row.weight_pct,
              pctText: f.pct(row.weight_pct, 1),
            }))}
          />
        </Panel>
        <Panel title={t("personal.marketCheck.purificationTitle")} description={t("personal.marketCheck.purificationIntro")}>
          <p className="text-2xl font-semibold tabular-nums text-mono">{f.bdt(d.purification.total)}</p>
        </Panel>
      </div>

      <Panel title={t("personal.marketCheck.holdingsTitle")} table>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("personal.name")}</TableHead>
              <TableHead className="text-end">{t("personal.marketCheck.weight")}</TableHead>
              <TableHead>{t("personal.shariah")}</TableHead>
              <TableHead className="hidden text-end md:table-cell">{t("market.scores.value")}</TableHead>
              <TableHead className="hidden text-end lg:table-cell">{t("personal.marketCheck.dividends")}</TableHead>
              <TableHead className="hidden text-end lg:table-cell">{t("personal.marketCheck.ratio")}</TableHead>
              <TableHead className="hidden text-end sm:table-cell">{t("personal.marketCheck.purification")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.holdings.map((h) => (
              <TableRow key={h.holding_id}>
                <TableCell>
                  <Link href={`/companies/${h.ticker}`} lang="en" className="font-medium text-primary hover:underline">
                    {h.ticker}
                  </Link>
                  <span className="block text-xs text-muted-foreground">{f.bdt(h.value)}</span>
                </TableCell>
                <TableCell className="text-end tabular-nums">{f.pct(h.weight_pct, 1)}</TableCell>
                <TableCell>
                  <ShariahBadge status={h.shariah} />
                </TableCell>
                <TableCell className="hidden text-end tabular-nums md:table-cell">{f.pct(h.rate_sensitivity_pct, 2, true)}</TableCell>
                <TableCell className="hidden text-end tabular-nums lg:table-cell">{f.bdt(h.dividends_12m)}</TableCell>
                <TableCell className="hidden text-end tabular-nums lg:table-cell">{f.pct(h.non_permissible_income_pct, 2)}</TableCell>
                <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.bdt(h.purification)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>

      <Panel title={t("personal.marketCheck.shockTitle")} description={t("personal.marketCheck.shockIntro")} table>
        {d.shock_exposure.length === 0 ? (
          <div className="p-5">
            <Empty>{t("market.events.empty")}</Empty>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("market.events.title")}</TableHead>
                <TableHead className="text-end">{t("market.events.ret1")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("market.events.ret5")}</TableHead>
                <TableHead className="text-end">{t("market.events.ret20")}</TableHead>
                <TableHead className="hidden text-end md:table-cell">{t("market.events.maxDd")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.shock_exposure.map((e) => (
                <TableRow key={e.event_id}>
                  <TableCell>
                    <Link href={`/events/${e.slug}`} className="text-primary hover:underline">
                      {pick(e, "title", locale)}
                    </Link>
                    <span className="block text-xs text-muted-foreground">
                      {f.date(e.t0)} · {t("personal.marketCheck.coverage", { pct: f.pct(e.coverage_pct, 0) })}
                    </span>
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(e.ret_1, 2, true)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(e.ret_5, 2, true)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(e.ret_20, 2, true)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums md:table-cell">{f.pct(e.max_dd_60, 2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </PersonalShell>
  );
}
