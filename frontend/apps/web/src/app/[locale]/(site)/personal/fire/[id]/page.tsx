import { type FirePlanDetail, type MarketEvent, SCENARIO_PRESETS } from "@analysisace/core";
import { notFound } from "next/navigation";

import { deleteFirePlanAction, deleteScenarioAction, runScenarioAction } from "@/app/actions/personal";
import { Empty, Facts, Panel, Stat, StatGrid } from "@/components/personal/display";
import { DeleteButton } from "@/components/personal/forms";
import { LineChart } from "@/components/personal/line-chart";
import { ScenarioForm } from "@/components/personal/scenario-form";
import { PersonalShell } from "@/components/personal/shell";
import { ApiError } from "@/lib/api";
import { get, hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, enumOptions, setup } from "@/lib/personal-page";

/** At most this many what-ifs are drawn beside the base case, so the chart stays readable. */
const MAX_DRAWN = 3;

/** One FIRE plan: its projection (FR17.2, FR17.3) and what-ifs against it (F18). */
export default async function FirePlanPage({ params }: PageProps<{ id: string }>) {
  const { locale, id } = await params;
  const { ctx, t, f } = await setup(locale, `/personal/fire/${id}`);
  const trail = [{ label: t("personal.sections.fire"), href: "/personal/fire" }];
  if (!ctx.household) return <PersonalShell ctx={ctx} title={t("personal.sections.fire")}>{null}</PersonalShell>;

  let detail: FirePlanDetail;
  try {
    detail = await hh<FirePlanDetail>(ctx, `/fire/plans/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const events = await load(get<MarketEvent[]>(ctx, "/events"));
  const { plan, scenarios } = detail;
  const hid = ctx.household.id;
  const inputs = plan.inputs;
  const drawn = scenarios.slice(0, MAX_DRAWN);
  const scenarioLabel = (preset: string, params: Record<string, string>) => {
    const name = enumLabel(t, "scenario", preset);
    if (preset === "EVENT_REPLAY") return `${name}: ${(locale === "bn" ? params.event_title_bn : params.event_title_en) ?? ""}`;
    const value = params.fall_pct ?? params.pct ?? params.years ?? params.points;
    return value ? `${name} (${f.num(value, 1)})` : name;
  };

  // One row per year of the base projection; each what-if adds its own column.
  const points = plan.projection.map((p, i) => ({
    label: t("personal.fire.ageLabel", { age: f.num(p.age, 0) }),
    values: {
      base: p.net_worth,
      ...Object.fromEntries(drawn.map((s) => [s.id, s.result.projection[i]?.net_worth ?? null])),
    },
  }));

  return (
    <PersonalShell
      ctx={ctx}
      title={plan.name}
      description={t("personal.fire.planIntro")}
      trail={trail}
      actions={
        ctx.canEdit && (
          <DeleteButton action={deleteFirePlanAction.bind(null, hid, id)} label={t("personal.fire.deletePlan")} title={t("personal.fire.deletePlan")} />
        )
      }
    >
      <StatGrid>
        <Stat label={t("personal.fire.fireNumber")} value={f.compact(plan.fire_number)} hint={f.bdt(plan.fire_number)} />
        <Stat label={t("personal.fire.fireAge")} value={plan.fire_age ? f.num(plan.fire_age, 1) : t("personal.fire.notReached")} hint={t("personal.fire.fireAgeHint")} />
        <Stat label={t("personal.fire.realReturn")} value={f.pct(String(inputs.real_return_pct ?? ""))} hint={t("personal.fire.realReturnHint")} />
        <Stat label={t("personal.fire.netWorth")} value={f.compact(String(inputs.net_worth ?? ""))} />
      </StatGrid>

      <Panel title={t("personal.fire.projection")} description={t("personal.fire.projectionIntro")}>
        <LineChart
          title={t("personal.fire.projection")}
          kind="bdt"
          series={[
            { key: "base", label: t("personal.fire.baseCase") },
            ...drawn.map((s) => ({ key: s.id, label: scenarioLabel(s.preset, s.params) })),
          ]}
          points={points}
          reference={{ value: plan.fire_number, label: t("personal.fire.fireNumber") }}
        />
      </Panel>

      <Panel title={t("personal.fire.inputs")}>
        <Facts
          items={[
            { label: t("personal.fire.netWorth"), value: f.bdt(String(inputs.net_worth)) },
            { label: t("personal.fire.monthlySavings"), value: f.bdt(String(inputs.monthly_savings)) },
            { label: t("personal.fire.yearlyExpenses"), value: f.bdt(String(inputs.yearly_expenses)) },
            { label: t("personal.fire.return"), value: f.pct(String(inputs.nominal_return_pct)) },
            { label: t("personal.fire.inflation"), value: f.pct(String(inputs.inflation_pct)) },
            { label: t("personal.fire.withdrawal"), value: f.pct(String(inputs.withdrawal_rate_pct), 1) },
            { label: t("personal.fire.age"), value: f.num(String(inputs.current_age), 0) },
            { label: t("personal.fire.marketShare"), value: f.pct(String(inputs.market_share_pct ?? "")) },
          ]}
        />
      </Panel>

      <Panel title={t("personal.fire.scenarios")} description={t("personal.fire.scenariosIntro")}>
        <div className="flex flex-col gap-5">
          {scenarios.length === 0 ? (
            <Empty>{t("personal.fire.noScenarios")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {scenarios.map((s) => (
                <li key={s.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="font-medium text-mono">{scenarioLabel(s.preset, s.params)}</p>
                    <p className="text-secondary-foreground">
                      {s.result.fire_age
                        ? t("personal.fire.scenarioAge", {
                            age: f.num(s.result.fire_age, 1),
                            change: f.num(s.result.fire_age_change ?? "0", 1),
                          })
                        : t("personal.fire.scenarioNever")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("personal.fire.worstYear", {
                        value: f.compact(s.result.worst_year_net_worth),
                        base: f.compact(s.result.base_worst_year_net_worth),
                      })}
                      {s.result.depleted_age && ` · ${t("personal.fire.depleted", { age: f.num(s.result.depleted_age, 0) })}`}
                    </p>
                  </div>
                  {ctx.canEdit && (
                    <DeleteButton action={deleteScenarioAction.bind(null, hid, id, s.id)} label={t("personal.fire.deleteScenario")} title={t("personal.fire.deleteScenario")} />
                  )}
                </li>
              ))}
            </ul>
          )}
          {ctx.canEdit && (
            <ScenarioForm
              action={runScenarioAction.bind(null, hid, id)}
              presets={enumOptions(t, "scenario", SCENARIO_PRESETS)}
              events={events.ok ? events.data.map((e) => ({ value: e.id, label: `${locale === "bn" ? e.title_bn : e.title_en} (${f.date(e.t0)})` })) : []}
            />
          )}
        </div>
      </Panel>
    </PersonalShell>
  );
}
