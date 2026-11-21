import type { CorporateActionRow, DataIssues } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import {
  addCorporateActionAction,
  addMetalPriceAction,
  importSeriesAction,
  runAnalyticsAction,
  runQualityChecksAction,
  setIssueStatusAction,
} from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionButton, ActionForm, FieldGrid, FileField, SelectField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { adminSetup } from "@/lib/market";
import { seriesLabel } from "@/lib/market-labels";
import { todayDhaka } from "@/lib/personal-page";

const STATUSES = ["OPEN", "RESOLVED", "IGNORED"] as const;
const ACTION_TYPES = ["BONUS", "RIGHTS", "SPLIT", "CASH_DIVIDEND"] as const;
const METALS = ["GOLD_22K_BDT_PER_GRAM", "SILVER_BDT_PER_GRAM"] as const;

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ status?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.data" });
  return { title: t("metaTitle"), robots: { index: false } };
}

/** Review queue (PRD section 8), manual metal prices (Q9), CSV loads and corporate actions. */
export default async function AdminDataPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { t, f, user, admin } = await adminSetup(locale, "/admin/data", "DATA_REVIEW");
  const raw = (await searchParams).status;
  const wanted = Array.isArray(raw) ? raw[0] : raw;
  const status = wanted === "ALL" ? "" : (STATUSES.find((s) => s === wanted) ?? "OPEN");
  const [issues, actions] = await Promise.all([
    admin<DataIssues>(`/admin/data-issues?status=${status}&limit=100`),
    admin<CorporateActionRow[]>("/admin/corporate-actions"),
  ]);
  const openTotal = issues.ok ? Object.values(issues.data.open_by_dataset).reduce((a, b) => a + b, 0) : 0;

  return (
    <AdminShell title={t("adminMarket.data.title")} description={t("adminMarket.data.intro")}>
      <Panel
        title={t("adminMarket.data.issuesTitle")}
        description={t("adminMarket.data.open", { n: openTotal })}
        actions={
          <>
            {(["ALL", ...STATUSES] as const).map((s) => (
              <Button key={s} size="sm" variant={(s === "ALL" ? "" : s) === status ? "primary" : "outline"} asChild>
                <Link href={{ pathname: "/admin/data", query: { status: s } }}>
                  {s === "ALL" ? t("adminMarket.data.allStatuses") : t(`adminMarket.data.status.${s}`)}
                </Link>
              </Button>
            ))}
            <ActionButton action={runQualityChecksAction}>{t("adminMarket.data.runChecks")}</ActionButton>
          </>
        }
        table
      >
        {!issues.ok ? (
          <div className="p-5">
            <LoadError code={issues.code} />
          </div>
        ) : issues.data.items.length === 0 ? (
          <div className="p-5">
            <Empty>{t("adminMarket.data.noIssues")}</Empty>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("adminMarket.data.check")}</TableHead>
                <TableHead className="hidden sm:table-cell">{t("adminMarket.data.dataset")}</TableHead>
                <TableHead>{t("adminMarket.data.detail")}</TableHead>
                <TableHead className="hidden md:table-cell">{t("adminMarket.data.date")}</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {issues.data.items.map((issue) => (
                <TableRow key={issue.id}>
                  <TableCell className="text-xs font-medium" lang="en">
                    {issue.check_name}
                    <Badge variant="secondary" appearance="light" size="sm" className="ms-2">
                      {t(`adminMarket.data.status.${issue.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden text-xs sm:table-cell" lang="en">
                    {issue.dataset}
                    {issue.entity && ` · ${issue.entity}`}
                  </TableCell>
                  <TableCell className="text-sm" lang="en">
                    {issue.detail}
                  </TableCell>
                  <TableCell className="hidden tabular-nums md:table-cell">{f.date(issue.date)}</TableCell>
                  <TableCell className="text-end">
                    <div className="flex flex-wrap justify-end gap-1">
                      {issue.status === "OPEN" ? (
                        <>
                          <ActionButton action={setIssueStatusAction.bind(null, issue.id, "RESOLVED")}>
                            {t("adminMarket.data.resolve")}
                          </ActionButton>
                          <ActionButton action={setIssueStatusAction.bind(null, issue.id, "IGNORED")} variant="ghost">
                            {t("adminMarket.data.ignore")}
                          </ActionButton>
                        </>
                      ) : (
                        <ActionButton action={setIssueStatusAction.bind(null, issue.id, "OPEN")} variant="ghost">
                          {t("adminMarket.data.reopen")}
                        </ActionButton>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("adminMarket.data.metalTitle")} description={t("adminMarket.data.metalIntro")}>
          <ActionForm action={addMetalPriceAction} submitLabel={t("adminMarket.data.add")} success={t("common.saved")}>
            <SelectField
              label={t("adminMarket.data.series")}
              name="code"
              options={METALS.map((code) => ({ value: code, label: seriesLabel(t, code) }))}
            />
            <Field label={t("adminMarket.data.date")} name="date" type="date" defaultValue={todayDhaka()} required />
            <Field label={t("adminMarket.data.price")} name="value" inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,4})?" required />
            <Field label={t("adminMarket.data.note")} name="note" maxLength={300} />
          </ActionForm>
        </Panel>

        <Panel title={t("adminMarket.data.csvTitle")} description={t("adminMarket.data.csvIntro")}>
          <ActionForm action={importSeriesAction} submitLabel={t("adminMarket.data.load")}>
            <SelectField
              label={t("adminMarket.data.kindLabel")}
              name="kind"
              options={(["index", "macro"] as const).map((k) => ({ value: k, label: t(`adminMarket.data.kind.${k}`) }))}
            />
            <Field label={t("adminMarket.data.sourceName")} name="source_name" maxLength={200} required />
            <Field label={t("adminMarket.data.sourceUrl")} name="source_url" type="url" maxLength={500} />
            <TextareaField label={t("adminMarket.data.content")} name="content" rows={5} placeholder={"code,date,value\nDSEX,2026-11-12,6420.15"} />
            <FileField label={t("adminMarket.data.file")} name="file" accept=".csv,text/csv" />
          </ActionForm>
        </Panel>
      </div>

      <Panel title={t("adminMarket.data.actionsTitle")} description={t("adminMarket.data.actionsIntro")}>
        <div className="flex flex-col gap-6">
          <ActionForm action={addCorporateActionAction} submitLabel={t("adminMarket.data.addAction")} success={t("common.saved")}>
            <FieldGrid>
              <Field label={t("adminMarket.data.ticker")} name="ticker" maxLength={20} required lang="en" />
              <Field label={t("adminMarket.data.exDate")} name="ex_date" type="date" required />
              <SelectField
                label={t("adminMarket.data.type")}
                name="type"
                options={ACTION_TYPES.map((a) => ({ value: a, label: t(`adminMarket.data.actionType.${a}`) }))}
              />
              <Field label={t("adminMarket.data.ratio")} name="ratio" inputMode="decimal" hint={t("adminMarket.data.ratioHint")} />
              <Field label={t("adminMarket.data.amount")} name="amount" inputMode="decimal" hint={t("adminMarket.data.amountHint")} />
              <Field label={t("adminMarket.data.sourceName")} name="source_name" maxLength={200} required />
              <Field label={t("adminMarket.data.sourceUrl")} name="source_url" type="url" maxLength={500} />
            </FieldGrid>
          </ActionForm>
          {!actions.ok ? (
            <LoadError code={actions.code} />
          ) : actions.data.length === 0 ? (
            <Empty>{t("adminMarket.data.noActions")}</Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("adminMarket.data.ticker")}</TableHead>
                  <TableHead>{t("adminMarket.data.exDate")}</TableHead>
                  <TableHead>{t("adminMarket.data.type")}</TableHead>
                  <TableHead className="text-end">{t("adminMarket.data.ratio")}</TableHead>
                  <TableHead className="text-end">{t("adminMarket.data.amount")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {actions.data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell lang="en">{a.ticker}</TableCell>
                    <TableCell className="tabular-nums">{f.date(a.ex_date)}</TableCell>
                    <TableCell>
                      {t.has(`adminMarket.data.actionType.${a.type}` as never) ? t(`adminMarket.data.actionType.${a.type}` as never) : a.type}
                    </TableCell>
                    <TableCell className="text-end tabular-nums">{f.num(a.ratio, 4)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.num(a.amount, 2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </Panel>

      {user.permissions.includes("CONFIG_MANAGE") && (
        <Panel title={t("adminMarket.data.analyticsTitle")} description={t("adminMarket.data.analyticsIntro")}>
          <ActionButton action={runAnalyticsAction} variant="primary" size="md">
            {t("adminMarket.data.run")}
          </ActionButton>
        </Panel>
      )}
    </AdminShell>
  );
}
