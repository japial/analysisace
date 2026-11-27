import type { Member, RecordedIncome, TaxSnapshot } from "@analysisace/core";

import { createTaxAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, FieldGrid, SelectField } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, memberOptions, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("tax");

/** Wealth statement and income summary for a tax year (FR13.5, FR13.6). */
export default async function TaxPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/tax");
  const title = t("personal.sections.tax");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [snapshots, members, year] = await Promise.all([
    load(hh<TaxSnapshot[]>(ctx, "/tax/snapshots")),
    load(hh<Member[]>(ctx, "/members")),
    load(hh<{ tax_year: string }>(ctx, "/tax/current-year")),
  ]);
  const memberName = (id: string) =>
    (members.ok && members.data.find((m) => m.id === id)?.display_name) || "—";
  const you = members.ok ? members.data.find((m) => m.is_you) : undefined;
  const recorded =
    you && year.ok
      ? await load(hh<RecordedIncome>(ctx, `/tax/recorded-income?member_id=${you.id}&tax_year=${year.data.tax_year}`))
      : null;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.tax.intro")}>
      <Alert variant="info" appearance="light" role="note">
        <AlertDescription>{t("personal.tax.notAdvice")}</AlertDescription>
      </Alert>

      {ctx.canEdit && members.ok && (
        <Panel title={t("personal.tax.newTitle")} description={t("personal.tax.newIntro")}>
          <ActionForm action={createTaxAction.bind(null, ctx.household.id)} submitLabel={t("personal.tax.prepare")}>
            <FieldGrid>
              <SelectField label={t("personal.member")} name="member_id" options={memberOptions(members.data)} defaultValue={you?.id} />
              <Field label={t("personal.tax.year")} name="tax_year" defaultValue={year.ok ? year.data.tax_year : ""} pattern="\d{4}-\d{2}" placeholder="2026-27" required hint={t("personal.tax.yearHint")} />
              <Field label={t("personal.tax.salary")} name="salary_income" type="number" inputMode="decimal" min="0" step="0.01" hint={t("personal.tax.salaryHint")} />
              <Field label={t("personal.tax.otherIncome")} name="other_income" type="number" inputMode="decimal" min="0" step="0.01" hint={t("personal.tax.otherIncomeHint")} />
            </FieldGrid>
            {recorded?.ok && year.ok && (
              <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-secondary-foreground">
                <p>
                  {t("personal.tax.recorded", {
                    year: year.data.tax_year,
                    salary: f.bdt(recorded.data.salary),
                    other: f.bdt(recorded.data.other),
                  })}
                </p>
                {recorded.data.not_counted.length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("personal.tax.notCounted", {
                      items: recorded.data.not_counted
                        .map((n) => `${enumLabel(t, "incomeType", n.kind)} ${f.bdt(n.amount)}`)
                        .join(", "),
                    })}
                  </p>
                )}
                {recorded.data.unassigned !== "0.00" && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("personal.tax.unassigned", { amount: f.bdt(recorded.data.unassigned) })}
                  </p>
                )}
                <Link href="/personal/income" className="mt-1 inline-block text-xs text-primary hover:underline">
                  {t("personal.tax.openIncome")}
                </Link>
              </div>
            )}
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.tax.history")} table>
        {!snapshots.ok ? (
          <div className="p-5"><LoadError code={snapshots.code} /></div>
        ) : snapshots.data.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.tax.empty")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.tax.year")}</TableHead>
                <TableHead>{t("personal.member")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("personal.tax.netWealth")}</TableHead>
                <TableHead className="text-end">{t("personal.tax.income")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {snapshots.data.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link href={`/personal/tax/${s.id}`} className="text-primary hover:underline">{s.tax_year}</Link>
                    <span className="block text-xs text-muted-foreground">{f.date(s.as_of)}</span>
                  </TableCell>
                  <TableCell>{memberName(s.member_id)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.bdt(s.items.totals.net_wealth_cost)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(s.items.totals.income)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </PersonalShell>
  );
}
