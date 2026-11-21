import type { AuditEntry, JobRun, Page } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AdminShell } from "@/components/admin/shell";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { adminSetup } from "@/lib/market";

const PAGE_SIZE = 50;

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.audit" });
  return { title: t("metaTitle"), robots: { index: false } };
}

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** Short "key: before → after" lines for an audit entry. */
function changes(entry: AuditEntry): string {
  const keys = new Set([...Object.keys(entry.before ?? {}), ...Object.keys(entry.after ?? {})]);
  return [...keys]
    .map((key) => {
      const before = entry.before?.[key];
      const after = entry.after?.[key];
      const show = (v: unknown) => (v === undefined ? "" : JSON.stringify(v));
      return before === undefined ? `${key}: ${show(after)}` : `${key}: ${show(before)} → ${show(after)}`;
    })
    .join("; ");
}

/** The audit log viewer (permission AUDIT_VIEW) and recent job runs. */
export default async function AdminAuditPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { t, f, admin } = await adminSetup(locale, "/admin/audit", "AUDIT_VIEW");
  const query = await searchParams;
  const action = first(query.action).slice(0, 60);
  const since = /^\d{4}-\d{2}-\d{2}$/.test(first(query.since)) ? first(query.since) : "";
  const page = Math.max(1, Number.parseInt(first(query.page), 10) || 1);
  const params_ = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
  if (action) params_.set("action", action);
  if (since) params_.set("since", since);

  const [entries, jobs] = await Promise.all([
    admin<Page<AuditEntry>>(`/admin/audit?${params_}`),
    admin<JobRun[]>("/admin/jobs?limit=30"),
  ]);
  const pageHref = (target: number) => ({
    pathname: "/admin/audit",
    query: { ...(action && { action }), ...(since && { since }), ...(target > 1 && { page: String(target) }) },
  });

  return (
    <AdminShell title={t("adminMarket.audit.title")} description={t("adminMarket.audit.intro")}>
      <Panel title={t("adminMarket.audit.title")} table>
        <form className="flex flex-wrap items-end gap-3 border-b border-border p-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="audit-action" className="text-sm font-medium text-mono">
              {t("adminMarket.audit.action")}
            </label>
            <Input id="audit-action" name="action" defaultValue={action} maxLength={60} className="w-56" lang="en" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="audit-since" className="text-sm font-medium text-mono">
              {t("adminMarket.audit.since")}
            </label>
            <Input id="audit-since" name="since" type="date" defaultValue={since} className="w-44" />
          </div>
          <Button type="submit" variant="outline">
            {t("adminMarket.audit.filter")}
          </Button>
        </form>
        {!entries.ok ? (
          <div className="p-5">
            <LoadError code={entries.code} />
          </div>
        ) : entries.data.items.length === 0 ? (
          <div className="p-5">
            <Empty>{t("adminMarket.audit.none")}</Empty>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("adminMarket.audit.at")}</TableHead>
                  <TableHead>{t("adminMarket.audit.action")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("adminMarket.audit.entity")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("adminMarket.audit.change")}</TableHead>
                  <TableHead className="hidden xl:table-cell">{t("adminMarket.audit.actor")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.data.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap tabular-nums">{f.date(entry.at, true)}</TableCell>
                    <TableCell className="text-xs" lang="en">
                      {entry.action}
                    </TableCell>
                    <TableCell className="hidden text-xs md:table-cell" lang="en">
                      {entry.entity}
                      {entry.entity_id && ` · ${entry.entity_id}`}
                    </TableCell>
                    <TableCell className="hidden max-w-md break-words font-mono text-xs lg:table-cell" lang="en">
                      {changes(entry)}
                    </TableCell>
                    <TableCell className="hidden font-mono text-xs xl:table-cell">{entry.actor}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3 text-sm text-secondary-foreground">
              <span>
                {t("adminMarket.audit.pageOf", {
                  from: entries.data.offset + 1,
                  to: entries.data.offset + entries.data.items.length,
                  total: entries.data.total,
                })}
              </span>
              <div className="flex gap-2">
                {page > 1 && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={pageHref(page - 1)}>{t("common.previous")}</Link>
                  </Button>
                )}
                {entries.data.offset + entries.data.items.length < entries.data.total && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={pageHref(page + 1)}>{t("common.next")}</Link>
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </Panel>

      <Panel title={t("adminMarket.audit.jobsTitle")} table>
        {!jobs.ok ? (
          <div className="p-5">
            <LoadError code={jobs.code} />
          </div>
        ) : jobs.data.length === 0 ? (
          <div className="p-5">
            <Empty>{t("adminMarket.audit.noJobs")}</Empty>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("adminMarket.audit.job")}</TableHead>
                <TableHead>{t("adminMarket.audit.started")}</TableHead>
                <TableHead>{t("adminMarket.audit.status")}</TableHead>
                <TableHead className="hidden lg:table-cell">{t("adminMarket.audit.detail")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.data.map((job) => (
                <TableRow key={job.id}>
                  <TableCell className="text-xs" lang="en">
                    {job.job}
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">{f.date(job.started_at, true)}</TableCell>
                  <TableCell>
                    <Badge variant={job.status === "SUCCESS" ? "success" : "destructive"} appearance="light" size="sm">
                      {job.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden max-w-md break-words font-mono text-xs lg:table-cell" lang="en">
                    {job.detail ? JSON.stringify(job.detail) : ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </AdminShell>
  );
}
