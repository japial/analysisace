import type { Financials, ShariahAdminItem } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { reviewFinancialsAction } from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Empty, LoadError, Panel, ShariahBadge } from "@/components/personal/display";
import { ActionButton } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { request } from "@/lib/api";
import { formatterFor } from "@/lib/fmt";
import { settle } from "@/lib/market";
import { getSessionToken, requireUser } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.shariah" });
  return { title: t("metaTitle"), robots: { index: false } };
}

/**
 * F1 administration. Admins with SHARIAH_OVERRIDE see every company; reviewers with
 * DATA_REVIEW see the figures waiting for review. The API checks both again.
 */
export default async function AdminShariahPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const user = await requireUser(locale as Locale, "/admin/shariah");
  const canOverride = user.permissions.includes("SHARIAH_OVERRIDE");
  const canReview = user.permissions.includes("DATA_REVIEW");
  if (!canOverride && !canReview) notFound();
  const token = (await getSessionToken()) ?? "";
  const t = await getTranslations();
  const f = formatterFor(locale);

  const [companies, pending] = await Promise.all([
    canOverride ? settle(request<ShariahAdminItem[]>("/admin/shariah", { token })) : null,
    canReview
      ? settle(request<{ items: Financials[] }>("/admin/financials?reviewed=false&limit=100", { token }))
      : null,
  ]);

  return (
    <AdminShell title={t("adminMarket.shariah.title")} description={t("adminMarket.shariah.intro")}>
      {pending && (
        <Panel title={t("adminMarket.shariah.unreviewed")} table>
          {!pending.ok ? (
            <div className="p-5">
              <LoadError code={pending.code} />
            </div>
          ) : pending.data.items.length === 0 ? (
            <div className="p-5">
              <Empty>{t("adminMarket.shariah.noFinancials")}</Empty>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("adminMarket.shariah.company")}</TableHead>
                  <TableHead>{t("adminMarket.shariah.periodEnd")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("adminMarket.shariah.sourceName")}</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {pending.data.items.map((fin) => (
                  <TableRow key={fin.id}>
                    <TableCell>
                      <Link href={`/admin/shariah/${fin.ticker}`} lang="en" className="font-medium text-primary hover:underline">
                        {fin.ticker}
                      </Link>
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {f.date(fin.period_end)} · {t(`adminMarket.shariah.periodTypes.${fin.period_type as "ANNUAL"}`)}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {fin.source_url ? (
                        <a href={fin.source_url} rel="noopener" className="underline">
                          {fin.source_name}
                        </a>
                      ) : (
                        fin.source_name
                      )}
                    </TableCell>
                    <TableCell className="text-end">
                      <ActionButton action={reviewFinancialsAction.bind(null, fin.id)}>{t("adminMarket.shariah.review")}</ActionButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>
      )}

      {companies && (
        <Panel title={t("adminMarket.shariah.company")} table>
          {!companies.ok ? (
            <div className="p-5">
              <LoadError code={companies.code} />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("adminMarket.shariah.company")}</TableHead>
                  <TableHead>{t("adminMarket.shariah.status")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("adminMarket.shariah.screen")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("adminMarket.shariah.classificationTitle")}</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {companies.data.map((c) => (
                  <TableRow key={c.ticker}>
                    <TableCell>
                      <span lang="en" className="font-medium text-mono">
                        {c.ticker}
                      </span>
                      <span lang="en" className="block text-xs text-muted-foreground">
                        {c.name}
                      </span>
                    </TableCell>
                    <TableCell>{c.status ? <ShariahBadge status={c.status} /> : "—"}</TableCell>
                    <TableCell className="hidden md:table-cell">{c.screen_status ? <ShariahBadge status={c.screen_status} /> : "—"}</TableCell>
                    <TableCell className="hidden text-sm lg:table-cell">
                      {c.classification
                        ? c.classification.stage1_pass
                          ? t("market.screen.stage1Pass")
                          : t(`market.screen.activity.${(c.classification.activity ?? "weapons") as "weapons"}`)
                        : t("market.screen.stage1None")}
                      {c.unreviewed_financials > 0 && (
                        <Badge variant="warning" appearance="light" size="sm" className="ms-2">
                          {t("adminMarket.shariah.pending", { n: c.unreviewed_financials })}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-end">
                      <Link href={`/admin/shariah/${c.ticker}`} className="text-sm text-primary hover:underline">
                        {t("adminMarket.shariah.manage")}
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>
      )}
    </AdminShell>
  );
}
