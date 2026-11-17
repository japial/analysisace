import type { Envelope, FireDefaults, FirePlan, Member } from "@analysisace/core";

import { createFirePlanAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, FieldGrid, SelectField } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, memberOptions, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("fire");

interface Props extends PageProps {
  searchParams: Promise<{ illiquid?: string }>;
}

/** FIRE calculator (F17). A projection of the person's own assumptions, not a forecast. */
export default async function FirePage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/fire");
  const title = t("personal.sections.fire");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const illiquid = (await searchParams).illiquid === "1";
  const [defaults, plans, members] = await Promise.all([
    load(hh<Envelope<FireDefaults>>(ctx, `/fire/defaults?include_illiquid=${illiquid}`)),
    load(hh<FirePlan[]>(ctx, "/fire/plans")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const d = defaults.ok ? defaults.data.data : null;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.fire.intro")}>
      <Panel title={t("personal.fire.plans")} table>
        {!plans.ok ? (
          <div className="p-5"><LoadError code={plans.code} /></div>
        ) : plans.data.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.fire.noPlans")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.name")}</TableHead>
                <TableHead className="text-end">{t("personal.fire.fireNumber")}</TableHead>
                <TableHead className="text-end">{t("personal.fire.fireAge")}</TableHead>
                <TableHead className="hidden sm:table-cell">{t("personal.date")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.data.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/personal/fire/${p.id}`} className="text-primary hover:underline">{p.name}</Link>
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{f.compact(p.fire_number)}</TableCell>
                  <TableCell className="text-end tabular-nums">{p.fire_age ? f.num(p.fire_age, 1) : t("personal.fire.notReached")}</TableCell>
                  <TableCell className="hidden sm:table-cell">{f.date(p.computed_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>

      {ctx.canEdit && (
        <Panel
          title={t("personal.fire.newTitle")}
          description={t("personal.fire.newIntro")}
          footnote={defaults.ok ? { asOf: defaults.data.as_of, sources: defaults.data.sources } : undefined}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href={{ pathname: "/personal/fire", query: illiquid ? {} : { illiquid: "1" } }}>
                {illiquid ? t("personal.fire.excludeIlliquid") : t("personal.fire.includeIlliquid")}
              </Link>
            </Button>
          }
        >
          {!d ? (
            <LoadError code={defaults.ok ? "UNAVAILABLE" : defaults.code} />
          ) : (
            <ActionForm action={createFirePlanAction.bind(null, ctx.household.id)} submitLabel={t("personal.fire.project")}>
                  <>
                    <p className="text-sm text-muted-foreground">
                      {illiquid
                        ? t("personal.fire.illiquidIncluded")
                        : t("personal.fire.illiquidExcluded", { amount: f.bdt(d.illiquid_excluded) })}
                    </p>
                    <FieldGrid>
                      <Field label={t("personal.name")} name="name" defaultValue={t("personal.fire.defaultName")} maxLength={120} required />
                      <SelectField label={t("personal.member")} name="member_id" options={members.ok ? memberOptions(members.data) : []} placeholder={t("personal.wholeHousehold")} />
                      <Field label={t("personal.fire.netWorth")} name="net_worth" type="number" inputMode="decimal" step="0.01" defaultValue={d.net_worth} required hint={t("personal.fire.netWorthHint")} />
                      <Field label={t("personal.fire.monthlySavings")} name="monthly_savings" type="number" inputMode="decimal" min="0" step="0.01" required />
                      <Field label={t("personal.fire.yearlyExpenses")} name="yearly_expenses" type="number" inputMode="decimal" min="0.01" step="0.01" defaultValue={d.yearly_expenses === "0.00" ? "" : d.yearly_expenses} required hint={t("personal.fire.yearlyExpensesHint")} />
                      <Field label={t("personal.fire.return")} name="nominal_return_pct" type="number" inputMode="decimal" step="0.01" defaultValue={d.nominal_return_pct ?? ""} required hint={enumLabel(t, "returnBasis", d.nominal_return_basis)} />
                      <Field label={t("personal.fire.inflation")} name="inflation_pct" type="number" inputMode="decimal" step="0.01" defaultValue={d.inflation_pct ?? ""} required hint={t("personal.fire.inflationHint", { months: d.inflation_months })} />
                      <Field label={t("personal.fire.withdrawal")} name="withdrawal_rate_pct" type="number" inputMode="decimal" min="0.1" max="50" step="0.1" defaultValue={d.withdrawal_rate_pct} required hint={t("personal.fire.withdrawalHint")} />
                      <Field label={t("personal.fire.age")} name="current_age" type="number" min="10" max="99" step="1" defaultValue={d.current_age ?? ""} required />
                    </FieldGrid>
                    {illiquid && <input type="hidden" name="include_illiquid" value="on" />}
                  </>
            </ActionForm>
          )}
        </Panel>
      )}
    </PersonalShell>
  );
}
