import {
  type CompanyEvent,
  type CompanyShariah,
  type Envelope,
  type Score,
  formatBDT,
  formatDate,
  formatNumber,
} from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { BadgeCheck, Percent, Zap } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { DataFootnote } from "@/components/data-footnote";
import { Disclaimer } from "@/components/disclaimer";
import { Toolbar } from "@/components/layout/toolbar";
import { CompanyEventsSection, ScoresSection, ShariahSection } from "@/components/market/company-sections";
import { WatchButton } from "@/components/market/watch-button";
import { ShariahBadge } from "@/components/personal/display";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getCompany } from "@/lib/api";
import { digitsFor } from "@/lib/locale";
import { loadPublic } from "@/lib/market";

interface Props {
  params: Promise<{ locale: string; ticker: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ticker } = await params;
  const result = await getCompany(ticker).catch(() => null);
  if (!result) return {};
  return { title: `${result.data.ticker}: ${result.data.name}` };
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-base font-semibold tabular-nums text-mono">{children}</dd>
    </div>
  );
}

export default async function CompanyPage({ params }: Props) {
  const { locale: rawLocale, ticker } = await params;
  const locale = rawLocale as Locale;
  setRequestLocale(locale);

  const result = await getCompany(ticker);
  if (!result) notFound();
  const code = encodeURIComponent(result.data.ticker);
  const [shariah, scores, events] = await Promise.all([
    loadPublic<Envelope<CompanyShariah>>(`/companies/${code}/shariah`),
    loadPublic<Envelope<Score[]>>(`/companies/${code}/scores`),
    loadPublic<Envelope<CompanyEvent[]>>(`/companies/${code}/events`),
  ]);

  const t = await getTranslations();
  const company = result.data;
  const price = company.latest_price;
  const digits = digitsFor(locale);

  return (
    <>
      <Toolbar
        title={company.name}
        breadcrumbs={[
          { label: t("nav.home"), href: "/" },
          { label: t("companies.title"), href: "/companies" },
          { label: company.ticker },
        ]}
      >
        {!company.is_active && (
          <Badge variant="warning" appearance="light">
            {t("company.inactive")}
          </Badge>
        )}
        <WatchButton ticker={company.ticker} />
      </Toolbar>

      <div className="container flex flex-col gap-5 lg:gap-7.5">
        <Disclaimer />

        {/* At a glance: the facts a visitor looks for first, in one card. */}
        <Card>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 lg:grid-cols-6">
              <Fact label={t("market.screen.shown")}>
                {shariah.ok ? <ShariahBadge status={shariah.data.data.status} /> : t("common.notAvailable")}
              </Fact>
              <Fact label={t("company.latestClose")}>
                {price ? formatBDT(price.close, { digits }) : t("common.notAvailable")}
              </Fact>
              <Fact label={t("company.tradingDay")}>
                {price ? formatDate(price.date, { language: locale, digits }) : t("common.notAvailable")}
              </Fact>
              <Fact label={t("company.volume")}>
                {price?.volume == null ? t("common.notAvailable") : formatNumber(price.volume, { digits })}
              </Fact>
              <Fact label={t("company.sector")}>{company.sector ?? t("companies.sectorUnknown")}</Fact>
              <Fact label={t("company.listed")}>
                {company.listing_date
                  ? formatDate(company.listing_date, { language: locale, digits })
                  : t("common.notAvailable")}
              </Fact>
            </dl>
            {!price && <p className="mt-4 text-sm text-secondary-foreground">{t("company.noPrice")}</p>}
          </CardContent>
          <div className="border-t border-border px-5 py-3">
            <DataFootnote asOf={result.as_of} sources={result.sources} />
          </div>
        </Card>

        {/* Three analyses, one at a time, so the page does not scroll for ever. */}
        <Tabs defaultValue="shariah" className="flex flex-col gap-5">
          <TabsList variant="line" className="overflow-x-auto">
            <TabsTrigger value="shariah">
              <BadgeCheck aria-hidden="true" />
              {t("market.screen.title")}
            </TabsTrigger>
            <TabsTrigger value="rates">
              <Percent aria-hidden="true" />
              {t("market.scores.title")}
            </TabsTrigger>
            <TabsTrigger value="events">
              <Zap aria-hidden="true" />
              {t("market.events.companyTitle")}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="shariah">
            <ShariahSection result={shariah} />
          </TabsContent>
          <TabsContent value="rates">
            <ScoresSection result={scores} />
          </TabsContent>
          <TabsContent value="events">
            <CompanyEventsSection result={events} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
