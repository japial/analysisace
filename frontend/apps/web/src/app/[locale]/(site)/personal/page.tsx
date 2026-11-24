import type {
  AceSummary,
  AceTrend,
  SetupStatus,
  FireProgress,
  Allocation,
  CostSummary,
  Envelope,
  GoalProgress,
  Notifications,
  PortfolioSummary,
} from "@analysisace/core";
import { ArrowRight } from "lucide-react";

import { recordNetWorthAction } from "@/app/actions/personal";
import { AceSummaryPanel } from "@/components/personal/ace-summary";
import { AceTrendPanel } from "@/components/personal/ace-trend";
import { FireProgressPanel } from "@/components/personal/fire-progress";
import { GettingStarted } from "@/components/personal/getting-started";
import { Empty, LoadError, Panel, ShareBars, Stat, StatGrid } from "@/components/personal/display";
import { ActionButton } from "@/components/personal/forms";
import { SectionShortcuts } from "@/components/personal/section-shortcuts";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { get, hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("overview");

/**
 * "My money" overview: progress toward FIRE first (F17, D21), then the ACE summary, net
 * worth, who owns what, goals and new notices (F14, F19, F20, F24).
 */
export default async function PersonalOverviewPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal");
  if (!ctx.household) {
    return <PersonalShell ctx={ctx} title={t("personal.sections.overview")} root>{null}</PersonalShell>;
  }

  const [setupStatus, fire, ace, summary, allocation, trend, goals, costs, notices] = await Promise.all([
    load(hh<SetupStatus>(ctx, "/setup/status")),
    load(hh<Envelope<FireProgress>>(ctx, "/fire/progress")),
    load(hh<Envelope<AceSummary>>(ctx, "/ace/summary")),
    load(hh<Envelope<PortfolioSummary>>(ctx, "/portfolio/summary")),
    load(hh<Envelope<Allocation>>(ctx, "/portfolio/allocation")),
    load(hh<Envelope<AceTrend>>(ctx, "/ace/trend?months=12")),
    load(hh<Envelope<GoalProgress[]>>(ctx, "/goals")),
    load(hh<Envelope<CostSummary>>(ctx, "/costs/summary?months=12")),
    load(get<Notifications>(ctx, "/notifications?unread_only=true&limit=5")),
  ]);

  return (
    <PersonalShell
      ctx={ctx}
      root
      title={t("personal.sections.overview")}
      description={t("personal.overview.intro")}
    >
      {setupStatus.ok && <GettingStarted status={setupStatus.data} locale={locale} canEdit={ctx.canEdit} />}

      {fire.ok ? <FireProgressPanel progress={fire.data} locale={locale} /> : <LoadError code={fire.code} />}

      {ace.ok ? <AceSummaryPanel summary={ace.data} locale={locale} /> : <LoadError code={ace.code} />}

      {!summary.ok ? (
        <LoadError code={summary.code} />
      ) : (
        <>
          <StatGrid>
            <Stat label={t("personal.overview.netWorth")} value={f.compact(summary.data.data.net_worth)} hint={f.bdt(summary.data.data.net_worth)} />
            <Stat label={t("personal.overview.assets")} value={f.compact(summary.data.data.assets)} hint={f.bdt(summary.data.data.assets)} />
            <Stat label={t("personal.overview.liabilities")} value={f.compact(summary.data.data.liabilities)} hint={f.bdt(summary.data.data.liabilities)} />
            <Stat
              label={t("personal.overview.costs12")}
              value={costs.ok ? f.compact(costs.data.data.trailing_12_months) : "—"}
              hint={t("personal.overview.costs12Hint")}
            />
          </StatGrid>

          <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2 lg:gap-7.5">
            <Panel
              title={t("personal.overview.byClass")}
              actions={
                <Button variant="outline" size="sm" asChild>
                  <Link href="/personal/allocation">
                    {t("personal.sections.allocation")}
                    <ArrowRight />
                  </Link>
                </Button>
              }
              footnote={{ asOf: summary.data.as_of, sources: summary.data.sources }}
            >
              {!allocation.ok ? (
                <LoadError code={allocation.code} />
              ) : allocation.data.data.by_class.length === 0 ? (
                <Empty>{t("personal.overview.empty")}</Empty>
              ) : (
                <ShareBars
                  rows={allocation.data.data.by_class.map((row) => ({
                    key: row.key,
                    label: enumLabel(t, "assetClass", row.key),
                    value: f.compact(row.value),
                    pct: row.pct,
                    pctText: f.pct(row.pct, 1),
                  }))}
                />
              )}
            </Panel>

            <Panel title={t("personal.overview.byMember")} description={t("personal.overview.byMemberIntro")} table>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="px-5 py-2.5 text-start font-medium">{t("personal.member")}</th>
                    <th className="px-5 py-2.5 text-end font-medium">{t("personal.overview.netWorth")}</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.data.data.by_member.map((m) => (
                    <tr key={m.member_id} className="border-b border-border last:border-0">
                      <td className="px-5 py-2.5 text-mono">{m.display_name}</td>
                      <td className="px-5 py-2.5 text-end tabular-nums">{f.bdt(m.net_worth)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        </>
      )}

      {trend.ok ? (
        <AceTrendPanel
          trend={trend.data}
          locale={locale}
          actions={
            ctx.canEdit && (
              <ActionButton action={recordNetWorthAction.bind(null, ctx.household.id)}>
                {t("personal.overview.recordToday")}
              </ActionButton>
            )
          }
        />
      ) : (
        <LoadError code={trend.code} />
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel
          title={t("personal.sections.goals")}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/personal/goals">
                {t("personal.overview.seeAll")}
                <ArrowRight />
              </Link>
            </Button>
          }
        >
          {!goals.ok ? (
            <LoadError code={goals.code} />
          ) : goals.data.data.length === 0 ? (
            <Empty>{t("personal.goals.empty")}</Empty>
          ) : (
            <ShareBars
              rows={goals.data.data.slice(0, 4).map((g) => ({
                key: g.goal.id,
                label: g.goal.name,
                value: g.reached
                  ? t("personal.goals.reached")
                  : g.goal.type === "FIRE_AGE"
                    ? t("personal.fire.ageLabel", { age: f.num(g.current, 1) })
                    : f.compact(g.current),
                pct: g.progress_pct ?? "0",
                pctText: f.pct(g.progress_pct, 0),
              }))}
            />
          )}
        </Panel>

        <Panel
          title={t("personal.overview.notices")}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/personal/alerts">
                {t("personal.overview.seeAll")}
                <ArrowRight />
              </Link>
            </Button>
          }
        >
          {!notices.ok ? (
            <LoadError code={notices.code} />
          ) : notices.data.items.length === 0 ? (
            <Empty>{t("personal.alerts.noUnread")}</Empty>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {notices.data.items.map((n) => (
                <li key={n.id} className="text-secondary-foreground">
                  {enumLabel(t, "alertType", n.type)} · {f.date(n.created_at)}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <SectionShortcuts />
    </PersonalShell>
  );
}
