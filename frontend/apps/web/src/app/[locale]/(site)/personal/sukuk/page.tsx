import type {
  BankExposure,
  CalendarEntry,
  Envelope,
  IslamicHolding,
  ProductComparison,
  SukukIssue,
} from "@analysisace/core";
import { TriangleAlert } from "lucide-react";

import { Empty, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import { PersonalShell } from "@/components/personal/shell";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { get, hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("sukuk");

/**
 * Sukuk and Islamic bank investments (F26): own holdings with profit so far, maturities and
 * auctions, how bank money is spread, and published product rates beside the T-bill yield
 * and inflation. Information only.
 */
export default async function SukukPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/sukuk");
  const title = t("personal.sections.sukuk");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [holdings, calendar, safety, compare, issues] = await Promise.all([
    load(hh<Envelope<IslamicHolding[]>>(ctx, "/sukuk/holdings")),
    load(hh<CalendarEntry[]>(ctx, "/sukuk/calendar?days=365")),
    load(hh<BankExposure[]>(ctx, "/sukuk/bank-safety")),
    load(get<Envelope<ProductComparison>>(ctx, "/islamic-products/compare")),
    load(get<Envelope<SukukIssue[]>>(ctx, "/sukuk/issues")),
  ]);

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.sukuk.intro")}>
      <Panel
        title={t("personal.sukuk.holdings")}
        description={t("personal.sukuk.holdingsIntro")}
        table
        footnote={holdings.ok ? { asOf: holdings.data.as_of, sources: holdings.data.sources } : undefined}
      >
        {!holdings.ok ? (
          <div className="p-5"><LoadError code={holdings.code} /></div>
        ) : holdings.data.data.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.sukuk.noHoldings")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.name")}</TableHead>
                <TableHead className="text-end">{t("personal.value")}</TableHead>
                <TableHead className="hidden text-end md:table-cell">{t("personal.sukuk.rate")}</TableHead>
                <TableHead className="hidden text-end md:table-cell">{t("personal.sukuk.profitAtRate")}</TableHead>
                <TableHead className="hidden text-end lg:table-cell">{t("personal.portfolio.profitReceived")}</TableHead>
                <TableHead className="hidden lg:table-cell">{t("personal.portfolio.maturity")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {holdings.data.data.map((h) => (
                <TableRow key={h.id}>
                  <TableCell>
                    <Link href={`/personal/portfolio/holdings/${h.id}`} className="text-primary hover:underline">{h.name}</Link>
                    <span className="block text-xs text-muted-foreground">{h.institution} · {enumLabel(t, "instrument", h.type)}</span>
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(h.household_value)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums md:table-cell">
                    {f.pct(h.rate_pct)}
                    {!h.rate_is_final && <span className="block text-xs text-muted-foreground">{t("personal.sukuk.provisional")}</span>}
                  </TableCell>
                  <TableCell className="hidden text-end tabular-nums md:table-cell">{f.bdt(h.profit_at_rate)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums lg:table-cell">
                    {f.bdt(h.profit_received)}
                    {h.tax_deducted !== "0.00" && <span className="block text-xs text-muted-foreground">{t("personal.sukuk.taxAtSource", { amount: f.bdt(h.tax_deducted) })}</span>}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {f.date(h.maturity_date)}
                    {h.days_to_maturity !== null && <span className="block text-xs text-muted-foreground">{t("personal.sukuk.daysLeft", { days: f.num(h.days_to_maturity, 0) })}</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.sukuk.calendar")} description={t("personal.sukuk.calendarIntro")}>
          {!calendar.ok ? (
            <LoadError code={calendar.code} />
          ) : calendar.data.length === 0 ? (
            <Empty>{t("personal.sukuk.calendarEmpty")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {calendar.data.map((c, i) => (
                <li key={`${c.date}-${i}`} className="flex flex-wrap items-start justify-between gap-2 py-2.5">
                  <div>
                    <p className="text-mono">{c.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {enumLabel(t, "calendarKind", c.kind)}
                      {c.institution ? ` · ${c.institution}` : ""}
                      {c.rate_pct ? ` · ${f.pct(c.rate_pct)}` : ""}
                    </p>
                  </div>
                  <div className="text-end">
                    <p className="text-mono">{f.date(c.date)}</p>
                    <p className="text-xs text-muted-foreground">{t("personal.sukuk.daysLeft", { days: f.num(c.days_away, 0) })}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title={t("personal.sukuk.bankSafety")} description={t("personal.sukuk.bankSafetyIntro")}>
          {!safety.ok ? (
            <LoadError code={safety.code} />
          ) : safety.data.length === 0 ? (
            <Empty>{t("personal.sukuk.noBanks")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {safety.data.map((b) => (
                <li key={b.bank} className="flex flex-col gap-1 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-mono">{b.bank}</span>
                    <span className="tabular-nums">{f.bdt(b.amount)} · {f.pct(b.share_pct, 1)}</span>
                  </div>
                  {b.status !== "NORMAL" && (
                    <div className="flex items-start gap-1.5 text-xs">
                      <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-destructive" aria-hidden="true" />
                      <div>
                        <Badge variant="warning" appearance="light" size="sm">{enumLabel(t, "bankStatus", b.status)}</Badge>{" "}
                        {locale === "bn" ? b.note_bn : b.note_en}
                        {b.source_links.map((link) => (
                          <a key={link.url} href={link.url} rel="noopener" className="ms-1 underline">{link.title}</a>
                        ))}
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {compare.ok && (
        <>
          <StatGrid>
            <Stat label={t("personal.sukuk.tbill")} value={f.pct(compare.data.data.tbill_pct)} hint={f.date(compare.data.data.tbill_date)} />
            <Stat label={t("personal.sukuk.inflation")} value={f.pct(compare.data.data.inflation_pct)} hint={f.date(compare.data.data.inflation_date)} />
          </StatGrid>
          <Panel
            title={t("personal.sukuk.compare")}
            description={t("personal.sukuk.compareIntro")}
            table
            footnote={{ asOf: compare.data.as_of, sources: compare.data.sources }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.sukuk.product")}</TableHead>
                  <TableHead className="text-end">{t("personal.sukuk.rate")}</TableHead>
                  <TableHead className="hidden text-end sm:table-cell">{t("personal.sukuk.realRate")}</TableHead>
                  <TableHead className="hidden text-end md:table-cell">{t("personal.sukuk.spread")}</TableHead>
                  <TableHead className="hidden text-end lg:table-cell">{t("personal.sukuk.tenor")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {compare.data.data.rows.map((r, i) => (
                  <TableRow key={`${r.issuer}-${r.name}-${i}`}>
                    <TableCell>
                      <span className="text-mono">{r.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {r.issuer} · {enumLabel(t, "productKind", r.kind)}
                      </span>
                    </TableCell>
                    <TableCell className="text-end tabular-nums">
                      {f.pct(r.rate_pct)}
                      {r.rate_is_provisional && <span className="block text-xs text-muted-foreground">{t("personal.sukuk.provisional")}</span>}
                    </TableCell>
                    <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(r.real_rate_pct, 2, true)}</TableCell>
                    <TableCell className="hidden text-end tabular-nums md:table-cell">{t("personal.allocation.points", { value: f.num(r.spread_over_tbill_pts, 2) })}</TableCell>
                    <TableCell className="hidden text-end lg:table-cell">{r.tenor_months ? t("personal.assets.months", { n: r.tenor_months }) : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Panel>
        </>
      )}

      {issues.ok && issues.data.data.length > 0 && (
        <Panel title={t("personal.sukuk.issues")} table footnote={{ asOf: issues.data.as_of, sources: issues.data.sources }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.name")}</TableHead>
                <TableHead className="text-end">{t("personal.sukuk.rate")}</TableHead>
                <TableHead className="hidden md:table-cell">{t("personal.portfolio.maturity")}</TableHead>
                <TableHead className="hidden md:table-cell">{t("personal.sukuk.auction")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {issues.data.data.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <span className="text-mono">{s.name}</span>
                    <span className="block text-xs text-muted-foreground">{s.issuer} · {s.structure}</span>
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(s.rate_pct)}</TableCell>
                  <TableCell className="hidden md:table-cell">{f.date(s.maturity_date)}</TableCell>
                  <TableCell className="hidden md:table-cell">{f.date(s.auction_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      )}
    </PersonalShell>
  );
}
