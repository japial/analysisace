import { type Envelope, GOAL_TYPES, type GoalProgress, type Member } from "@analysisace/core";
import { CircleCheck } from "lucide-react";

import { addGoalAction, deleteGoalAction, setGoalActiveAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, DeleteButton, FieldGrid, SelectField, ToggleSwitch } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, enumOptions, memberOptions, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("goals");

/** Goals and progress towards them (F19). */
export default async function GoalsPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/goals");
  const title = t("personal.sections.goals");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [goals, members] = await Promise.all([
    load(hh<Envelope<GoalProgress[]>>(ctx, "/goals")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const hid = ctx.household.id;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.goals.intro")}>
      <Panel
        title={t("personal.goals.listTitle")}
        footnote={goals.ok ? { asOf: goals.data.as_of, sources: goals.data.sources } : undefined}
      >
        {!goals.ok ? (
          <LoadError code={goals.code} />
        ) : goals.data.data.length === 0 ? (
          <Empty>{t("personal.goals.empty")}</Empty>
        ) : (
          <ul className="flex flex-col gap-5">
            {goals.data.data.map((g) => {
              const isAge = g.goal.type === "FIRE_AGE";
              const show = (v: string | null) => (isAge ? f.num(v, 1) : f.bdt(v));
              return (
                <li key={g.goal.id} className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-1.5 font-medium text-mono">
                        {g.reached && <CircleCheck className="size-4 text-primary" aria-hidden="true" />}
                        {g.goal.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {enumLabel(t, "goalType", g.goal.type)}
                        {g.goal.target_date && ` · ${t("personal.goals.by", { date: f.date(g.goal.target_date) })}`}
                        {g.days_left !== null && g.days_left >= 0 && ` · ${t("personal.sukuk.daysLeft", { days: f.num(g.days_left, 0) })}`}
                      </p>
                    </div>
                    {ctx.canEdit && (
                      <div className="flex items-center gap-2">
                        <ToggleSwitch action={setGoalActiveAction.bind(null, hid, g.goal.id)} checked={g.goal.is_active} label={t("personal.goals.active")} />
                        <DeleteButton action={deleteGoalAction.bind(null, hid, g.goal.id)} label={t("personal.goals.delete")} title={t("personal.goals.delete")} />
                      </div>
                    )}
                  </div>
                  <div
                    className="h-2 overflow-hidden rounded-full bg-muted"
                    role="progressbar"
                    aria-label={g.goal.name}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={g.progress_pct ? Math.min(100, Number(g.progress_pct)) : 0}
                  >
                    <div className="h-full rounded-full bg-primary" style={{ width: `min(100%, ${g.progress_pct ?? "0"}%)` }} />
                  </div>
                  <p className="text-sm text-secondary-foreground">
                    {g.reached
                      ? t("personal.goals.reached")
                      : t("personal.goals.progress", {
                          current: show(g.current),
                          target: show(g.target),
                          pct: f.pct(g.progress_pct, 0),
                        })}
                    {g.on_track === true && ` · ${t("personal.goals.onTrack")}`}
                    {g.on_track === false && ` · ${t("personal.goals.behind")}`}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      {ctx.canEdit && (
        <Panel title={t("personal.goals.addTitle")} description={t("personal.goals.addIntro")}>
          <ActionForm action={addGoalAction.bind(null, hid)} submitLabel={t("personal.goals.add")}>
            <FieldGrid>
              <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "goalType", GOAL_TYPES)} defaultValue="NET_WORTH" />
              <Field label={t("personal.name")} name="name" maxLength={120} required />
              <SelectField label={t("personal.member")} name="member_id" options={members.ok ? memberOptions(members.data) : []} placeholder={t("personal.wholeHousehold")} />
              <Field label={t("personal.goals.targetAmount")} name="target_amount" type="number" inputMode="decimal" min="0.01" step="0.01" hint={t("personal.goals.targetAmountHint")} />
              <Field label={t("personal.goals.targetDate")} name="target_date" type="date" />
              <Field label={t("personal.goals.targetAge")} name="target_age" type="number" min="18" max="100" step="1" hint={t("personal.goals.targetAgeHint")} />
            </FieldGrid>
            <p className="text-xs text-muted-foreground">{t("personal.goals.savingsHint")}</p>
          </ActionForm>
        </Panel>
      )}
    </PersonalShell>
  );
}
