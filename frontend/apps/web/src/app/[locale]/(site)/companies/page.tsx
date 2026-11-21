import type { Company, Envelope, Page } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { DataFootnote } from "@/components/data-footnote";
import { Toolbar } from "@/components/layout/toolbar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTable, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { listCompanies } from "@/lib/api";

const PAGE_SIZE = 200;

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "companies" });
  return { title: t("metaTitle"), description: t("intro") };
}

async function loadCompanies(query: string): Promise<Envelope<Page<Company>> | null> {
  try {
    return await listCompanies({ q: query || undefined, limit: PAGE_SIZE });
  } catch (error) {
    console.error("Could not load companies", error);
    return null;
  }
}

export default async function CompaniesPage({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const { q } = await searchParams;
  const query = (Array.isArray(q) ? q[0] : q)?.trim() ?? "";

  const t = await getTranslations();
  const result = await loadCompanies(query);
  const page = result?.data;

  return (
    <>
      <Toolbar
        title={t("companies.title")}
        description={t("companies.intro")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("companies.title") }]}
      />
      <div className="container flex flex-col gap-5">
        {!page ? (
          <Alert variant="destructive" appearance="light" role="alert">
            <AlertDescription>{t("common.loadError")}</AlertDescription>
          </Alert>
        ) : (
          <Card>
            <CardHeader className="py-3.5">
              <CardTitle>
                {page.items.length < page.total
                  ? t("companies.showing", { shown: page.items.length, total: page.total })
                  : t("companies.count", { count: page.total })}
              </CardTitle>
              <form role="search" className="flex items-center gap-2.5">
                <label htmlFor="company-search" className="sr-only">
                  {t("companies.searchLabel")}
                </label>
                <Input
                  id="company-search"
                  type="search"
                  name="q"
                  defaultValue={query}
                  maxLength={50}
                  placeholder={t("companies.searchLabel")}
                  className="w-56 max-w-full"
                />
                <Button type="submit" variant="outline">
                  {t("companies.search")}
                </Button>
              </form>
            </CardHeader>

            {page.total === 0 ? (
              <CardContent className="flex flex-col items-start gap-2">
                <p>{query ? t("companies.noMatch", { query }) : t("companies.empty")}</p>
                {query && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/companies">{t("companies.clear")}</Link>
                  </Button>
                )}
              </CardContent>
            ) : (
              <CardTable>
                <CompanyTable page={page} />
              </CardTable>
            )}
          </Card>
        )}

        {result && <DataFootnote asOf={result.as_of} sources={result.sources} />}
      </div>
    </>
  );
}

async function CompanyTable({ page }: { page: Page<Company> }) {
  const t = await getTranslations("companies");
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("ticker")}</TableHead>
          <TableHead>{t("name")}</TableHead>
          <TableHead className="hidden sm:table-cell">{t("sector")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {page.items.map((company) => (
          <TableRow key={company.ticker}>
            <TableCell className="align-top font-medium">
              <Link
                href={`/companies/${company.ticker}`}
                lang="en"
                className="text-primary underline-offset-2 hover:underline"
              >
                {company.ticker}
              </Link>
            </TableCell>
            <TableCell>
              <span lang="en" className="text-mono">
                {company.name}
              </span>
              {/* On narrow screens the sector sits under the name. */}
              <span className="block text-sm text-muted-foreground sm:hidden">
                {company.sector ?? t("sectorUnknown")}
              </span>
            </TableCell>
            <TableCell className="hidden text-secondary-foreground sm:table-cell">
              {company.sector ?? t("sectorUnknown")}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
