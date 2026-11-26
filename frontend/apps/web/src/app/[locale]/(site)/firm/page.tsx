import type { FirmDetail, FirmSummary } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { FileText, Info, Sheet } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import {
  addFirmMemberAction,
  removeFirmLogoAction,
  removeFirmMemberAction,
  revokeApiKeyAction,
  setFirmDisclaimerAction,
  setFirmLogoAction,
  setFirmRoleAction,
} from "@/app/actions/firm";
import { Disclaimer } from "@/components/disclaimer";
import { ApiKeyForm } from "@/components/firm/api-key-form";
import { Field } from "@/components/form/form-parts";
import { Toolbar } from "@/components/layout/toolbar";
import { Empty, Panel } from "@/components/personal/display";
import { ActionForm, DeleteButton, FieldGrid, FileField, SelectField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { ApiError, request } from "@/lib/api";
import { downloadHref } from "@/lib/download";
import { formatterFor } from "@/lib/fmt";
import { requireToken, requireUser } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ id?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "firm" });
  return { title: t("metaTitle"), robots: { index: false } };
}

/**
 * The firm page (F9, D30): white-label weekly report and CSV exports for every member;
 * members, API keys, usage and report settings for the firm's admins. Missing (404) while
 * firm features are switched off, or for someone without a seat.
 */
export default async function FirmPage({ params, searchParams }: Props) {
  const { locale: raw } = await params;
  const locale = raw as Locale;
  setRequestLocale(locale);
  await requireUser(locale, "/firm");
  const token = await requireToken();

  let mine: FirmSummary[];
  try {
    mine = await request<FirmSummary[]>("/firms/mine", { token });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const wanted = (await searchParams).id;
  const chosen = mine.find((m) => m.id === wanted) ?? mine[0];
  if (!chosen) notFound();
  const firm = await request<FirmDetail>(`/firms/${chosen.id}`, { token });

  const t = await getTranslations();
  const f = formatterFor(locale);
  const admin = firm.role === "ADMIN";
  const base = `/firms/${firm.id}`;
  const roleOptions = (["MEMBER", "ADMIN"] as const).map((r) => ({ value: r, label: t(`firm.role.${r}`) }));
  const week = firm.report_weeks[0];

  return (
    <>
      <Toolbar
        title={firm.name}
        description={t("firm.intro")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("firm.metaTitle") }]}
      >
        <Badge variant="secondary" appearance="light">
          {t(`firm.role.${firm.role}`)}
        </Badge>
      </Toolbar>
      <div className="container flex flex-col gap-5 pb-10 lg:gap-7.5">
        {mine.length > 1 && (
          <nav aria-label={t("firm.switch")} className="flex flex-wrap gap-2">
            {mine.map((m) => (
              <Button key={m.id} variant={m.id === firm.id ? "primary" : "outline"} size="sm" asChild>
                <Link href={{ pathname: "/firm", query: { id: m.id } }}>{m.name}</Link>
              </Button>
            ))}
          </nav>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
          <Panel title={t("firm.reportTitle")} description={t("firm.reportIntro")}>
            {week ? (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-secondary-foreground">{t("firm.latestWeek", { date: f.date(week) })}</p>
                <div className="flex flex-wrap gap-2">
                  {(["en", "bn"] as const).map((lang) => (
                    <Button key={lang} variant="outline" size="sm" asChild>
                      <a href={downloadHref(locale, `${base}/reports/weekly.pdf?locale=${lang}&week=${week}`)} download>
                        <FileText />
                        {t(`firm.reportIn.${lang}`)}
                      </a>
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <Empty>{t("firm.noReport")}</Empty>
            )}
          </Panel>

          <Panel title={t("firm.exportsTitle")} description={t("firm.exportsIntro")}>
            <div className="flex flex-wrap gap-2">
              {(["shariah", "scores"] as const).map((dataset) => (
                <Button key={dataset} variant="outline" size="sm" asChild>
                  <a href={downloadHref(locale, `${base}/exports/${dataset}.csv`)} download>
                    <Sheet />
                    {t(`firm.export.${dataset}`)}
                  </a>
                </Button>
              ))}
            </div>
          </Panel>
        </div>

        <Panel
          title={t("firm.membersTitle")}
          description={t("firm.seats", { used: f.num(String(firm.members.length), 0), limit: f.num(String(firm.seat_limit), 0) })}
          table
        >
          <ul className="flex flex-col divide-y divide-border">
            {firm.members.map((m) => (
              <li key={m.user_id} className="flex flex-wrap items-end justify-between gap-3 px-5 py-3">
                <div className="flex min-w-48 flex-col gap-0.5 text-sm">
                  <span className="font-medium text-mono">{m.full_name}</span>
                  <span className="break-all text-secondary-foreground" lang="en">{m.email}</span>
                  {!admin && <span className="text-xs text-muted-foreground">{t(`firm.role.${m.role}`)}</span>}
                </div>
                {admin && (
                  <div className="flex items-end gap-2">
                    <ActionForm action={setFirmRoleAction.bind(null, firm.id, m.user_id)} submitLabel={t("common.save")} reset={false} className="flex-row flex-wrap items-end gap-2">
                      <SelectField label={t("firm.roleFor", { name: m.full_name })} name="role" options={roleOptions} defaultValue={m.role} />
                    </ActionForm>
                    <DeleteButton action={removeFirmMemberAction.bind(null, firm.id, m.user_id)} label={t("firm.remove")} title={t("firm.removeTitle", { name: m.full_name })} />
                  </div>
                )}
              </li>
            ))}
          </ul>
          {admin && (
            <div className="border-t border-border p-5">
              <ActionForm action={addFirmMemberAction.bind(null, firm.id)} submitLabel={t("firm.addMember")} success={t("common.saved")}>
                <FieldGrid>
                  <Field label={t("firm.email")} name="email" type="email" required hint={t("firm.emailHint")} />
                  <SelectField label={t("firm.roleLabel")} name="role" options={roleOptions} defaultValue="MEMBER" />
                </FieldGrid>
              </ActionForm>
            </div>
          )}
        </Panel>

        {admin && (
          <>
            <Panel title={t("firm.keysTitle")} description={t("firm.keysIntro")}>
              <div className="flex flex-col gap-5">
                {firm.api_keys.length === 0 ? (
                  <Empty>{t("firm.noKeys")}</Empty>
                ) : (
                  <ul className="flex flex-col divide-y divide-border">
                    {firm.api_keys.map((k) => (
                      <li key={k.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-mono">
                            {k.name} <code className="ms-1 text-xs text-muted-foreground" lang="en">{k.prefix}…</code>
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {t("firm.keyFacts", {
                              created: f.date(k.created_at),
                              used: k.last_used_at ? f.date(k.last_used_at, true) : t("firm.never"),
                              limit: f.num(String(k.rate_limit_per_minute), 0),
                            })}
                          </span>
                        </div>
                        {k.revoked_at ? (
                          <Badge variant="destructive" appearance="light">{t("firm.revoked")}</Badge>
                        ) : (
                          <DeleteButton action={revokeApiKeyAction.bind(null, firm.id, k.id)} label={t("firm.revoke")} title={t("firm.revokeTitle", { name: k.name })} />
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <ApiKeyForm firmId={firm.id} />
                <details className="rounded-lg border border-border p-3 text-sm">
                  <summary className="cursor-pointer font-medium text-mono">{t("firm.apiHowTo")}</summary>
                  <p className="mt-2 text-secondary-foreground">{t("firm.apiHowToBody")}</p>
                  <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 text-xs" lang="en">
                    {"GET /api/v1/firm-api/shariah\nGET /api/v1/firm-api/scores\nGET /api/v1/firm-api/macro-notes/latest?locale=bn\n\nX-API-Key: aace_…"}
                  </pre>
                </details>
              </div>
            </Panel>

            <Panel title={t("firm.usageTitle")} description={t("firm.usageIntro")} table>
              {firm.usage.length === 0 ? (
                <div className="p-5"><Empty>{t("firm.noUsage")}</Empty></div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("firm.date")}</TableHead>
                      <TableHead>{t("firm.key")}</TableHead>
                      <TableHead>{t("firm.endpoint")}</TableHead>
                      <TableHead className="text-end">{t("firm.calls")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {firm.usage.map((u) => (
                      <TableRow key={`${u.date}-${u.key}-${u.endpoint}`}>
                        <TableCell className="whitespace-nowrap">{f.date(u.date)}</TableCell>
                        <TableCell>{u.key}</TableCell>
                        <TableCell lang="en"><code className="text-xs">{u.endpoint}</code></TableCell>
                        <TableCell className="text-end tabular-nums">{f.num(String(u.calls), 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Panel>

            <Panel title={t("firm.brandingTitle")} description={t("firm.brandingIntro")}>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <ActionForm action={setFirmDisclaimerAction.bind(null, firm.id)} submitLabel={t("common.save")} success={t("common.saved")} reset={false}>
                  <TextareaField label={t("firm.disclaimer")} name="report_disclaimer" rows={4} maxLength={1000} defaultValue={firm.report_disclaimer ?? ""} hint={t("firm.disclaimerHint")} />
                </ActionForm>
                <div className="flex flex-col gap-3">
                  {firm.has_logo ? (
                    <div className="flex items-center gap-3">
                      {/* eslint-disable-next-line @next/next/no-img-element -- a small private image through the download route */}
                      <img src={downloadHref(locale, `${base}/logo`)} alt={t("firm.logoAlt", { name: firm.name })} className="h-12 w-auto rounded border border-border bg-white p-1" />
                      <DeleteButton action={removeFirmLogoAction.bind(null, firm.id)} label={t("firm.removeLogo")} title={t("firm.removeLogo")} />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">{t("firm.noLogo")}</p>
                  )}
                  <ActionForm action={setFirmLogoAction.bind(null, firm.id)} submitLabel={t("firm.uploadLogo")} success={t("common.saved")}>
                    <FileField label={t("firm.logo")} name="file" accept="image/png,image/jpeg" hint={t("firm.logoHint")} />
                  </ActionForm>
                </div>
              </div>
            </Panel>
          </>
        )}

        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Info className="size-3.5 shrink-0" aria-hidden="true" />
          {t("firm.ownScreen")}
        </p>
        <Disclaimer />
      </div>
    </>
  );
}
