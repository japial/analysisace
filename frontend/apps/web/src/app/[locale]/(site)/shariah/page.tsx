import type { Basket, Envelope, Page, ShariahListItem } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DataFootnote } from "@/components/data-footnote";
import { joinSeries } from "@/components/market/chart-data";
import { SegmentedLinks } from "@/components/market/segmented-links";
import { MarketShell } from "@/components/market/shell";
import { Empty, LoadError, Panel, ShariahBadge } from "@/components/personal/display";
import { SelectField } from "@/components/personal/forms";
import { LineChart } from "@/components/personal/line-chart";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { loadPublic, marketSetup } from "@/lib/market";
import { seriesLabel, statusLabel } from "@/lib/market-labels";

const STATUSES = ["COMPLIANT", "NON_COMPLIANT", "UNDER_REVIEW"] as const;
const SORTS = ["ticker", "status", "sector", "market_cap", "screened_at"] as const;
const YEARS = [1, 3, 5] as const;

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "market.shariah" });
  return { title: t("metaTitle"), description: t("intro") };
}

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** F2: the Shariah list (FR2.1) and the basket against DSES and DSEX (FR2.2). */
export default async function ShariahPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { t, f } = await marketSetup(locale);
  const query = await searchParams;
  const status = STATUSES.find((s) => s === first(query.status)) ?? "";
  const sort = SORTS.find((s) => s === first(query.sort)) ?? "ticker";
  const sector = first(query.sector);
  const q = first(query.q).slice(0, 50);
  const years = YEARS.find((y) => String(y) === first(query.years)) ?? 3;

  const params_ = new URLSearchParams({ sort, order: sort === "market_cap" || sort === "screened_at" ? "desc" : "asc" });
  if (status) params_.set("status", status);
  if (sector) params_.set("sector", sector);
  if (q) params_.set("q", q);

  const [list, all, basket] = await Promise.all([
    loadPublic<Envelope<Page<ShariahListItem>>>(`/shariah/list?${params_}`),
    loadPublic<Envelope<Page<ShariahListItem>>>("/shariah/list"),
    loadPublic<Envelope<Basket>>(`/shariah/basket?years=${years}`),
  ]);
  const sectors = all.ok
    ? [...new Set(all.data.data.items.map((i) => i.sector).filter((s): s is string => !!s))].sort()
    : [];
  const yearHref = (y: number) => ({
    pathname: "/shariah",
    query: { ...Object.fromEntries(params_), years: String(y) },
  });

  return (
    <MarketShell title={t("market.shariah.title")} description={t("market.shariah.intro")}>
      <Alert variant="info" appearance="light">
        <AlertDescription>{t("market.shariah.provisional")}</AlertDescription>
      </Alert>

      <Panel
        title={t("market.shariah.basketTitle")}
        description={t("market.shariah.basketIntro")}
        actions={
          <SegmentedLinks
            label={t("market.shariah.basketTitle")}
            options={YEARS.map((y) => ({ key: String(y), label: t("market.shariah.years", { n: y }), href: yearHref(y), current: y === years }))}
          />
        }
        footnote={basket.ok ? { asOf: basket.data.as_of, sources: basket.data.sources } : undefined}
      >
        {!basket.ok ? (
          <LoadError code={basket.code} />
        ) : Object.keys(basket.data.data.series).length === 0 ? (
          <Empty>{t("market.shariah.noBasket")}</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            <LineChart
              title={t("market.shariah.basketTitle")}
              kind="index"
              series={Object.keys(basket.data.data.series).map((code) => ({ key: code, label: seriesLabel(t, code) }))}
              points={joinSeries(basket.data.data.series, (d) => f.date(d))}
            />
            <p className="text-sm text-muted-foreground">
              {t("market.shariah.members", { n: basket.data.data.members.length })}:{" "}
              <span lang="en">{basket.data.data.members.join(", ")}</span>
            </p>
          </div>
        )}
      </Panel>

      <Panel
        title={list.ok ? t("market.shariah.listTitle", { n: list.data.data.total }) : t("market.shariah.title")}
        table
        footnote={list.ok ? { asOf: list.data.as_of, sources: list.data.sources } : undefined}
      >
        <form role="search" className="grid grid-cols-1 gap-3 border-b border-border p-5 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="shariah-q" className="text-sm font-medium text-mono">
              {t("market.shariah.search")}
            </label>
            <Input id="shariah-q" name="q" type="search" defaultValue={q} maxLength={50} />
          </div>
          <SelectField
            label={t("market.shariah.status")}
            name="status"
            defaultValue={status || undefined}
            placeholder={t("market.shariah.allStatuses")}
            options={STATUSES.map((s) => ({ value: s, label: statusLabel(t, s) }))}
          />
          <SelectField
            label={t("market.shariah.sector")}
            name="sector"
            defaultValue={sector || undefined}
            placeholder={t("market.shariah.allSectors")}
            options={sectors.map((s) => ({ value: s, label: s }))}
          />
          <SelectField
            label={t("market.shariah.sort")}
            name="sort"
            defaultValue={sort}
            options={SORTS.map((s) => ({ value: s, label: t(`market.shariah.sortBy.${s}`) }))}
          />
          <input type="hidden" name="years" value={years} />
          <Button type="submit" variant="outline" className="self-end">
            {t("market.shariah.apply")}
          </Button>
        </form>
        {!list.ok ? (
          <div className="p-5">
            <LoadError code={list.code} />
          </div>
        ) : list.data.data.items.length === 0 ? (
          <div className="p-5">
            <Empty>{t("market.shariah.empty")}</Empty>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("market.shariah.ticker")}</TableHead>
                <TableHead>{t("market.shariah.status")}</TableHead>
                <TableHead className="hidden md:table-cell">{t("market.shariah.sector")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("market.shariah.marketCap")}</TableHead>
                <TableHead className="hidden lg:table-cell">{t("market.shariah.screened")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data.data.items.map((item) => (
                <TableRow key={item.ticker}>
                  <TableCell>
                    <Link href={`/companies/${item.ticker}`} lang="en" className="font-medium text-primary hover:underline">
                      {item.ticker}
                    </Link>
                    <span lang="en" className="block text-sm text-secondary-foreground">
                      {item.name}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <ShariahBadge status={item.status} />
                      {item.overridden && (
                        <Badge variant="secondary" appearance="light" size="sm">
                          {t("market.shariah.overridden")}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden text-secondary-foreground md:table-cell">{item.sector ?? "—"}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.compact(item.market_cap)}</TableCell>
                  <TableCell className="hidden text-secondary-foreground lg:table-cell">{f.date(item.screened_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
      {!list.ok && all.ok && <DataFootnote asOf={all.data.as_of} sources={all.data.sources} />}
    </MarketShell>
  );
}
