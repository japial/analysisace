/**
 * Progress toward FIRE, the first thing on the My money overview (D21). Figures come from
 * `/fire/progress`; this component only formats them. With a plan it shows the projected
 * FIRE age; without one, an estimated FIRE number from a year of costs; without costs, the
 * first steps.
 */
import type { Envelope, FireProgress } from "@analysisace/core";
import { ArrowRight, Flame, PiggyBank, Target } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";

import { Panel } from "./display";

export async function FireProgressPanel({ progress, locale }: { progress: Envelope<FireProgress>; locale: string }) {
  const t = await getTranslations("personal.overview.fire");
  const f = formatterFor(locale);
  const d = progress.data;

  if (d.basis === "NO_COSTS") {
    return (
      <Panel title={t("title")} description={t("startIntro")}>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/personal/income">
              {t("recordIncome")}
              <ArrowRight className="rtl:rotate-180" />
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/personal/costs">{t("recordCosts")}</Link>
          </Button>
        </div>
      </Panel>
    );
  }

  const plan = d.plan;
  const headline =
    d.basis === "PLAN"
      ? {
          label: t("fireAge"),
          value: plan?.fire_age ? f.num(plan.fire_age, 0) : "—",
          hint:
            plan?.fire_age && plan.years_to_fire !== null
              ? t("yearsToGo", { years: f.num(plan.years_to_fire, 0), date: f.date(plan.computed_at) })
              : t("notReached"),
        }
      : {
          label: t("estimatedNumber"),
          value: f.compact(d.fire_number),
          hint: t("estimateHint", {
            costs: f.compact(d.yearly_costs),
            n: f.num(String(d.cost_months), 0),
            rate: f.pct(d.withdrawal_rate_pct, 1),
          }),
        };

  return (
    <Panel
      title={t("title")}
      description={d.basis === "PLAN" ? t("planIntro", { name: plan?.name ?? "" }) : t("estimateIntro")}
      actions={
        d.basis === "PLAN" && plan ? (
          <>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/personal/fire/${plan.id}`}>{t("openPlan")}</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/personal/fire">{t("updatePlan")}</Link>
            </Button>
          </>
        ) : (
          <Button size="sm" asChild>
            <Link href="/personal/fire">
              {t("makePlan")}
              <ArrowRight className="rtl:rotate-180" />
            </Link>
          </Button>
        )
      }
      footnote={{ asOf: progress.as_of, sources: progress.sources }}
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,15rem)_1fr] lg:items-center">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            {d.basis === "PLAN" ? <Flame className="size-4 text-primary" aria-hidden="true" /> : <Target className="size-4 text-primary" aria-hidden="true" />}
            {headline.label}
          </span>
          <span className="font-display text-4xl font-bold text-mono tabular-nums">{headline.value}</span>
          <span className="text-xs text-muted-foreground">{headline.hint}</span>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-secondary-foreground">{t("progress")}</span>
            <span className="text-lg font-semibold text-mono tabular-nums">{f.pct(d.progress_pct, 0)}</span>
          </div>
          <div
            className="h-3 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label={t("progress")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={d.progress_pct ? Number(d.progress_pct) : 0}
          >
            <div className="h-full rounded-full bg-gradient-to-r from-brand-teal-deep to-brand-teal" style={{ width: `${d.progress_pct ?? 0}%` }} />
          </div>
          <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
            <span>{t("investedOf", { invested: f.compact(d.investable), target: f.compact(d.fire_number) })}</span>
            {d.gap !== null && <span>{t("gap", { amount: f.compact(d.gap) })}</span>}
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-3 border-t border-border pt-3 text-sm">
            <div className="flex flex-col gap-0.5">
              <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <PiggyBank className="size-3.5 text-primary" aria-hidden="true" />
                {t("savingsRate")}
              </dt>
              <dd className="font-semibold text-mono tabular-nums">
                {d.savings_rate_pct === null ? (
                  <Link href="/personal/income" className="text-sm font-normal text-primary hover:underline">{t("addIncome")}</Link>
                ) : (
                  f.pct(d.savings_rate_pct, 0)
                )}
              </dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-xs text-muted-foreground">{t("savedMonth")}</dt>
              {/* Without income records there is no saving to show, only costs. */}
              <dd className="font-semibold text-mono tabular-nums">
                {d.savings_rate_pct === null ? "—" : f.compact(d.average_monthly_savings)}
              </dd>
            </div>
          </dl>
        </div>
      </div>
      {!d.include_illiquid && <p className="mt-4 text-xs text-muted-foreground">{t("illiquidNote")}</p>}
    </Panel>
  );
}
