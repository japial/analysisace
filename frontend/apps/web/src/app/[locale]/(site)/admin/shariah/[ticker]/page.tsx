import {
  type CompanyShariah,
  type Envelope,
  FINANCIAL_FIGURES,
  type Financials,
  STAGE1_ACTIVITIES,
  type ShariahAdminItem,
} from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import {
  reviewFinancialsAction,
  saveFinancialsAction,
  setBoardNoteAction,
  setClassificationAction,
  setOverrideAction,
} from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, ShariahBadge } from "@/components/personal/display";
import { ActionButton, ActionForm, CheckField, FieldGrid, SelectField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { getCompany, request } from "@/lib/api";
import { formatterFor } from "@/lib/fmt";
import { loadPublic, settle } from "@/lib/market";
import { statusLabel } from "@/lib/market-labels";
import { getSessionToken, requireUser } from "@/lib/session";

const PERIOD_TYPES = ["ANNUAL", "Q1", "Q2", "Q3"] as const;
const STATUSES = ["COMPLIANT", "NON_COMPLIANT", "UNDER_REVIEW"] as const;

interface Props {
  params: Promise<{ locale: string; ticker: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, ticker } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.shariah" });
  return { title: `${ticker.toUpperCase()}: ${t("metaTitle")}`, robots: { index: false } };
}

/** One company's F1 administration: figures and review, classification, override, note. */
export default async function AdminShariahCompanyPage({ params }: Props) {
  const { locale, ticker: rawTicker } = await params;
  setRequestLocale(locale as Locale);
  const ticker = rawTicker.toUpperCase();
  const user = await requireUser(locale as Locale, `/admin/shariah/${ticker}`);
  const canOverride = user.permissions.includes("SHARIAH_OVERRIDE");
  const canReview = user.permissions.includes("DATA_REVIEW");
  if (!canOverride && !canReview) notFound();
  const company = await getCompany(ticker);
  if (!company) notFound();
  const token = (await getSessionToken()) ?? "";
  const t = await getTranslations();
  const f = formatterFor(locale);

  const [financials, admin, shariah] = await Promise.all([
    canReview
      ? settle(request<{ items: Financials[] }>(`/admin/financials?ticker=${encodeURIComponent(ticker)}&limit=50`, { token }))
      : null,
    canOverride ? settle(request<ShariahAdminItem[]>("/admin/shariah", { token })) : null,
    loadPublic<Envelope<CompanyShariah>>(`/companies/${encodeURIComponent(ticker)}/shariah`),
  ]);
  const item = admin?.ok ? admin.data.find((c) => c.ticker === ticker) : undefined;

  return (
    <AdminShell
      title={`${ticker} · ${company.data.name}`}
      description={t("adminMarket.shariah.intro")}
      trail={[{ label: t("adminMarket.shariah.title"), href: "/admin/shariah" }]}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {shariah.ok ? (
          <>
            <span className="text-muted-foreground">{t("adminMarket.shariah.status")}:</span>
            <ShariahBadge status={shariah.data.data.status} />
            <span className="text-muted-foreground">{t("adminMarket.shariah.screen")}:</span>
            <ShariahBadge status={shariah.data.data.screen_status} />
          </>
        ) : (
          <span className="text-muted-foreground">{t("market.screen.notScreened")}</span>
        )}
        <Link href={`/companies/${ticker}`} className="ms-auto text-primary hover:underline">
          {t("market.screen.title")}
        </Link>
      </div>

      {canOverride && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3 lg:gap-7.5">
          <Panel title={t("adminMarket.shariah.classificationTitle")}>
            <ActionForm
              action={setClassificationAction.bind(null, ticker)}
              submitLabel={t("adminMarket.shariah.saveClassification")}
              success={t("common.saved")}
              reset={false}
            >
              <CheckField
                label={t("adminMarket.shariah.stage1")}
                name="stage1_pass"
                defaultChecked={item?.classification?.stage1_pass ?? true}
              />
              <SelectField
                label={t("adminMarket.shariah.activity")}
                name="activity"
                defaultValue={item?.classification?.activity ?? undefined}
                placeholder="—"
                options={STAGE1_ACTIVITIES.map((a) => ({ value: a, label: t(`market.screen.activity.${a}`) }))}
              />
              <TextareaField
                label={t("adminMarket.shariah.reason")}
                name="reason"
                required
                maxLength={2000}
                rows={3}
                defaultValue={item?.classification?.reason ?? ""}
              />
            </ActionForm>
          </Panel>

          <Panel title={t("adminMarket.shariah.overrideTitle")} description={t("adminMarket.shariah.overrideIntro")}>
            <ActionForm
              action={setOverrideAction.bind(null, ticker)}
              submitLabel={t("adminMarket.shariah.saveOverride")}
              success={t("common.saved")}
              reset={false}
            >
              <SelectField
                label={t("adminMarket.shariah.overrideStatus")}
                name="status"
                defaultValue={item?.override_status ?? "NONE"}
                options={[
                  { value: "NONE", label: t("adminMarket.shariah.noOverride") },
                  ...STATUSES.map((s) => ({ value: s, label: statusLabel(t, s) })),
                ]}
              />
              <TextareaField
                label={t("adminMarket.shariah.reason")}
                name="reason"
                required
                maxLength={2000}
                rows={3}
                defaultValue={item?.override_reason ?? ""}
              />
            </ActionForm>
          </Panel>

          <Panel title={t("adminMarket.shariah.noteTitle")}>
            <ActionForm
              action={setBoardNoteAction.bind(null, ticker)}
              submitLabel={t("adminMarket.shariah.saveNote")}
              success={t("common.saved")}
              reset={false}
            >
              <TextareaField
                label={t("adminMarket.shariah.note")}
                name="note"
                maxLength={5000}
                rows={5}
                defaultValue={item?.board_note ?? ""}
              />
            </ActionForm>
          </Panel>
        </div>
      )}

      {financials && (
        <Panel title={t("adminMarket.shariah.financialsTitle")} description={t("adminMarket.shariah.financialsIntro")}>
          <div className="flex flex-col gap-6">
            {!financials.ok ? (
              <LoadError code={financials.code} />
            ) : financials.data.items.length === 0 ? (
              <Empty>{t("adminMarket.shariah.noFinancials")}</Empty>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("adminMarket.shariah.periodEnd")}</TableHead>
                      {FINANCIAL_FIGURES.map((name) => (
                        <TableHead key={name} className="text-end">
                          {t(`market.screen.figures.${name}`)}
                        </TableHead>
                      ))}
                      <TableHead className="text-end">{t("adminMarket.shariah.shares")}</TableHead>
                      <TableHead>{t("adminMarket.shariah.sourceName")}</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {financials.data.items.map((fin) => (
                      <TableRow key={fin.id}>
                        <TableCell className="whitespace-nowrap tabular-nums">
                          {f.date(fin.period_end)}
                          <span className="block text-xs text-muted-foreground">
                            {t(`adminMarket.shariah.periodTypes.${fin.period_type as "ANNUAL"}`)}
                          </span>
                        </TableCell>
                        {FINANCIAL_FIGURES.map((name) => (
                          <TableCell key={name} className="text-end tabular-nums">
                            {f.compact(fin[name])}
                          </TableCell>
                        ))}
                        <TableCell className="text-end tabular-nums">
                          {f.num(fin.shares_outstanding === null ? null : String(fin.shares_outstanding), 0)}
                        </TableCell>
                        <TableCell className="text-sm">
                          {fin.source_url ? (
                            <a href={fin.source_url} rel="noopener" className="underline">
                              {fin.source_name}
                            </a>
                          ) : (
                            fin.source_name
                          )}
                          {fin.source_page !== null && ` · ${t("market.screen.page", { page: fin.source_page })}`}
                        </TableCell>
                        <TableCell className="text-end">
                          {fin.reviewed_at ? (
                            <Badge variant="success" appearance="light" size="sm">
                              {t("adminMarket.shariah.reviewed")}
                            </Badge>
                          ) : (
                            <ActionButton action={reviewFinancialsAction.bind(null, fin.id)}>
                              {t("adminMarket.shariah.review")}
                            </ActionButton>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <ActionForm
              action={saveFinancialsAction.bind(null, ticker)}
              submitLabel={t("adminMarket.shariah.saveFinancials")}
              success={t("common.saved")}
            >
              <FieldGrid>
                <Field label={t("adminMarket.shariah.periodEnd")} name="period_end" type="date" required />
                <SelectField
                  label={t("adminMarket.shariah.periodType")}
                  name="period_type"
                  options={PERIOD_TYPES.map((p) => ({ value: p, label: t(`adminMarket.shariah.periodTypes.${p}`) }))}
                />
                {FINANCIAL_FIGURES.map((name) => (
                  <Field
                    key={name}
                    label={t(`market.screen.figures.${name}`)}
                    name={name}
                    inputMode="decimal"
                    pattern="[0-9]+(\.[0-9]{1,2})?"
                  />
                ))}
                <Field label={t("adminMarket.shariah.shares")} name="shares_outstanding" inputMode="numeric" pattern="[0-9]+" />
                <Field label={t("adminMarket.shariah.sourceName")} name="source_name" maxLength={200} required />
                <Field label={t("adminMarket.shariah.sourceUrl")} name="source_url" type="url" maxLength={500} />
                <Field label={t("adminMarket.shariah.sourcePage")} name="source_page" inputMode="numeric" pattern="[0-9]+" />
              </FieldGrid>
            </ActionForm>
          </div>
        </Panel>
      )}
    </AdminShell>
  );
}
