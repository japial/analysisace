import type { Member, TaxSnapshot } from "@analysisace/core";
import { Download } from "lucide-react";
import { notFound } from "next/navigation";

import { deleteTaxAction } from "@/app/actions/personal";
import { Empty, Panel, Stat, StatGrid } from "@/components/personal/display";
import { DeleteButton } from "@/components/personal/forms";
import { PdfButton } from "@/components/personal/pdf-button";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { downloadHref } from "@/lib/download";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, setup } from "@/lib/personal-page";

/** One tax-year statement: assets at cost, debts, income and rebate-eligible purchases. */
export default async function TaxSnapshotPage({ params }: PageProps<{ id: string }>) {
  const { locale, id } = await params;
  const { ctx, t, f } = await setup(locale, `/personal/tax/${id}`);
  const trail = [{ label: t("personal.sections.tax"), href: "/personal/tax" }];
  if (!ctx.household) return <PersonalShell ctx={ctx} title={t("personal.sections.tax")}>{null}</PersonalShell>;

  let s: TaxSnapshot;
  try {
    s = await hh<TaxSnapshot>(ctx, `/tax/snapshots/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const members = await load(hh<Member[]>(ctx, "/members"));
  const member = members.ok ? members.data.find((m) => m.id === s.member_id) : undefined;
  const items = s.items;
  const hid = ctx.household.id;

  return (
    <PersonalShell
      ctx={ctx}
      title={t("personal.tax.snapshotTitle", { year: s.tax_year, name: member?.display_name ?? "—" })}
      description={t("personal.tax.period", { start: f.date(items.period.start), end: f.date(items.period.end) })}
      trail={trail}
      actions={
        <>
          <Button variant="outline" size="sm" asChild>
            <a href={downloadHref(locale, `/households/${hid}/tax/snapshots/${id}/export.csv`)} download>
              <Download />
              {t("personal.tax.csv")}
            </a>
          </Button>
          <PdfButton locale={locale} apiPath={`/households/${hid}/tax/snapshots/${id}/statement.pdf`} label={t("personal.pdf")} />
          {ctx.canEdit && (
            <DeleteButton action={deleteTaxAction.bind(null, hid, id)} label={t("personal.tax.delete")} title={t("personal.tax.delete")} />
          )}
        </>
      }
    >
      <StatGrid>
        <Stat label={t("personal.tax.assetsCost")} value={f.bdt(items.totals.assets_cost)} hint={t("personal.tax.assetsValue", { value: f.bdt(items.totals.assets_value) })} />
        <Stat label={t("personal.overview.liabilities")} value={f.bdt(items.totals.liabilities)} />
        <Stat label={t("personal.tax.netWealth")} value={f.bdt(items.totals.net_wealth_cost)} />
        <Stat label={t("personal.tax.income")} value={f.bdt(items.totals.income)} />
      </StatGrid>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.tax.incomeTitle")} table>
          <Table>
            <TableBody>
              {Object.entries(items.income).map(([key, amount]) => (
                <TableRow key={key}>
                  <TableCell>
                    {enumLabel(t, "incomeKind", key)}
                    {(key === "salary" || key === "other") && items.income_basis && (
                      <span className="ms-1 text-xs text-muted-foreground">
                        ({t(items.income_basis[key] === "RECORDS" ? "personal.tax.fromRecords" : "personal.tax.typedIn")})
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>

        <Panel title={t("personal.tax.deducted")} description={t("personal.tax.deductedIntro")}>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{t("personal.tax.deductedInYear")}</dt>
              <dd className="tabular-nums">{f.bdt(items.tax_deducted.in_year)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{t("personal.tax.deductedOnHoldings")}</dt>
              <dd className="tabular-nums">{f.bdt(items.tax_deducted.recorded_on_holdings)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-t border-border pt-2">
              <dt className="text-muted-foreground">{t("personal.tax.rebateEligible")}</dt>
              <dd className="tabular-nums">{f.bdt(items.rebate_eligible_total)}</dd>
            </div>
          </dl>
          {items.rebate_eligible.length > 0 && (
            <ul className="mt-3 list-disc ps-5 text-sm text-secondary-foreground">
              {items.rebate_eligible.map((r, i) => (
                <li key={i}>
                  {r.label}
                  {r.amount ? ` · ${f.bdt(r.amount)}` : ""}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title={t("personal.tax.assets")} description={t("personal.tax.assetsIntro")} table>
        {items.assets.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.overview.empty")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.name")}</TableHead>
                <TableHead className="hidden md:table-cell">{t("personal.allocation.assetClass")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("personal.zakat.share")}</TableHead>
                <TableHead className="text-end">{t("personal.cost")}</TableHead>
                <TableHead className="hidden text-end lg:table-cell">{t("personal.value")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.assets.map((a, i) => (
                <TableRow key={i}>
                  <TableCell>{a.label}</TableCell>
                  <TableCell className="hidden md:table-cell">{enumLabel(t, "assetClass", a.category)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(a.owner_pct, 0)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(a.cost)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums lg:table-cell">{f.bdt(a.value)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>

      {items.liabilities.length > 0 && (
        <Panel title={t("personal.portfolio.liabilities")} table>
          <Table>
            <TableBody>
              {items.liabilities.map((l, i) => (
                <TableRow key={i}>
                  <TableCell>
                    {l.label}
                    <span className="block text-xs text-muted-foreground">{enumLabel(t, "liabilityType", l.type)}</span>
                  </TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(l.owner_pct, 0)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(l.outstanding)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      )}
    </PersonalShell>
  );
}
