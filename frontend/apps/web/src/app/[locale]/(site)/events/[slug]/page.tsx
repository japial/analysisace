import type { Envelope, EventDetail, EventMetric } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";

import { MarketShell } from "@/components/market/shell";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { loadPublic, marketSetup, pick } from "@/lib/market";
import { eventTypeLabel } from "@/lib/market-labels";

interface Props {
  params: Promise<{ locale: string; slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  const result = await loadPublic<Envelope<EventDetail>>(`/events/${encodeURIComponent(slug)}`);
  if (!result.ok) return {};
  return { title: pick(result.data.data.event, "title", locale as Locale) };
}

async function MetricTable({ rows, link }: { rows: EventMetric[]; link: boolean }) {
  const t = await getTranslations();
  const f = formatterFor(await getLocale());
  const recovery = (m: EventMetric) =>
    m.sessions_to_recover === null
      ? t("market.events.notRecovered")
      : m.sessions_to_recover === 0
        ? t("market.events.neverFell")
        : t("market.events.sessions", { n: m.sessions_to_recover });
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("market.events.subject")}</TableHead>
          <TableHead className="text-end">{t("market.events.ret1")}</TableHead>
          <TableHead className="hidden text-end sm:table-cell">{t("market.events.ret5")}</TableHead>
          <TableHead className="text-end">{t("market.events.ret20")}</TableHead>
          <TableHead className="hidden text-end md:table-cell">{t("market.events.maxDd")}</TableHead>
          <TableHead className="hidden lg:table-cell">{t("market.events.recover")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m) => (
          <TableRow key={`${m.subject_type}-${m.subject}`}>
            <TableCell>
              {link ? (
                <Link href={`/companies/${m.subject}`} lang="en" className="font-medium text-primary hover:underline">
                  {m.subject}
                </Link>
              ) : (
                <span className="text-mono">{m.subject}</span>
              )}
            </TableCell>
            <TableCell className="text-end tabular-nums">{f.pct(m.ret_1, 2, true)}</TableCell>
            <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(m.ret_5, 2, true)}</TableCell>
            <TableCell className="text-end tabular-nums">{f.pct(m.ret_20, 2, true)}</TableCell>
            <TableCell className="hidden text-end tabular-nums md:table-cell">{f.pct(m.max_dd_60, 2)}</TableCell>
            <TableCell className="hidden text-secondary-foreground lg:table-cell">{recovery(m)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** F5: one event's metrics (FR5.2) and similar events (FR5.3). */
export default async function EventPage({ params }: Props) {
  const { locale, slug } = await params;
  const { t, f } = await marketSetup(locale);
  const result = await loadPublic<Envelope<EventDetail>>(`/events/${encodeURIComponent(slug)}`);
  if (!result.ok && result.status === 404) notFound();
  if (!result.ok) {
    return (
      <MarketShell title={t("market.events.title")} trail={[{ label: t("nav.events"), href: "/events" }]}>
        <LoadError code={result.code} />
      </MarketShell>
    );
  }
  const { event, metrics, similar } = result.data.data;
  const market = metrics.filter((m) => m.subject_type === "INDEX");
  const sectors = metrics.filter((m) => m.subject_type === "SECTOR");
  const stocks = metrics.filter((m) => m.subject_type === "TICKER");
  const footnote = { asOf: result.data.as_of, sources: result.data.sources };

  return (
    <MarketShell
      title={pick(event, "title", locale)}
      description={pick(event, "description", locale)}
      trail={[{ label: t("nav.events"), href: "/events" }]}
      actions={
        <Badge variant="secondary" appearance="light">
          {eventTypeLabel(t, event.type)} · {f.date(event.t0)}
        </Badge>
      }
    >
      <Panel title={t("market.events.market")} table={market.length > 0} footnote={footnote}>
        {market.length === 0 ? <Empty>{t("market.events.companyEmpty")}</Empty> : <MetricTable rows={market} link={false} />}
      </Panel>
      {sectors.length > 0 && (
        <Panel title={t("market.events.sectors")} table>
          <MetricTable rows={sectors} link={false} />
        </Panel>
      )}
      {stocks.length > 0 && (
        <Panel title={t("market.events.stocks")} table>
          <MetricTable rows={stocks} link />
        </Panel>
      )}

      <Panel title={t("market.events.similarTitle")} description={t("market.events.similarIntro")}>
        {similar.length === 0 ? (
          <Empty>{t("market.events.noSimilar")}</Empty>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {similar.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline gap-x-3">
                <span className="tabular-nums text-muted-foreground">{f.date(e.t0)}</span>
                <Link href={`/events/${e.slug}`} className="text-primary hover:underline">
                  {pick(e, "title", locale)}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {event.source_links.length > 0 && (
        <Panel title={t("market.events.sourcesTitle")}>
          <ul className="flex flex-col gap-1 text-sm">
            {event.source_links.map((link) => (
              <li key={link.url}>
                <a href={link.url} rel="noopener" className="text-primary underline">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </MarketShell>
  );
}
