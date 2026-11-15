import { formatBDT, formatDate, formatNumber } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { DataFootnote } from "@/components/data-footnote";
import { Disclaimer } from "@/components/disclaimer";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getCompany } from "@/lib/api";
import { digitsFor } from "@/lib/locale";

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
    <Card>
      <CardContent className="flex flex-col gap-1">
        <dt className="text-sm text-muted-foreground">{label}</dt>
        <dd className="text-xl font-semibold tabular-nums text-mono">{children}</dd>
      </CardContent>
    </Card>
  );
}

export default async function CompanyPage({ params }: Props) {
  const { locale: rawLocale, ticker } = await params;
  const locale = rawLocale as Locale;
  setRequestLocale(locale);

  const result = await getCompany(ticker);
  if (!result) notFound();

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
      </Toolbar>

      <div className="container flex flex-col gap-5 lg:gap-7.5">
        <Disclaimer />

        <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 lg:gap-7.5">
          {price ? (
            <>
              <Fact label={t("company.latestClose")}>{formatBDT(price.close, { digits })}</Fact>
              <Fact label={t("company.tradingDay")}>
                {formatDate(price.date, { language: locale, digits })}
              </Fact>
              <Fact label={t("company.volume")}>
                {price.volume === null
                  ? t("common.notAvailable")
                  : formatNumber(price.volume, { digits })}
              </Fact>
            </>
          ) : (
            <Card className="sm:col-span-2 lg:col-span-3">
              <CardContent className="text-secondary-foreground">{t("company.noPrice")}</CardContent>
            </Card>
          )}
          <Fact label={t("company.sector")}>{company.sector ?? t("companies.sectorUnknown")}</Fact>
          <Fact label={t("company.listed")}>
            {company.listing_date
              ? formatDate(company.listing_date, { language: locale, digits })
              : t("common.notAvailable")}
          </Fact>
        </dl>

        <Card>
          <CardHeader>
            <CardTitle>{t("company.shariahTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="text-secondary-foreground">
            {t("company.shariahPending")}
          </CardContent>
        </Card>

        <DataFootnote asOf={result.as_of} sources={result.sources} />
      </div>
    </>
  );
}
