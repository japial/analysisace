import type { CommunityBenchmarks } from "@analysisace/core";

import { Empty, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { get, load } from "@/lib/personal";
import { type PageProps, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("community");

/**
 * Anonymous comparison with people of a similar age (F21). Opt-in only; a group is shown
 * only when it is large enough that no one can be picked out (FR21.1).
 */
export default async function CommunityPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/community");
  const title = t("personal.sections.community");
  const consented = ctx.user.consents.COMMUNITY_BENCHMARKING?.granted ?? false;
  const result = consented ? await load(get<CommunityBenchmarks>(ctx, "/community/benchmarks")) : null;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.community.intro")}>
      {!result ? (
        <Panel title={t("personal.community.consentTitle")}>
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-secondary-foreground">{t("personal.community.consentBody")}</p>
            <Button variant="primary" size="sm" asChild>
              <Link href="/account">{t("personal.zakat.consentLink")}</Link>
            </Button>
          </div>
        </Panel>
      ) : !result.ok ? (
        <LoadError code={result.code} />
      ) : !result.data.has_plan ? (
        <Panel title={t("personal.community.noPlanTitle")}>
          <div className="flex flex-col items-start gap-3">
            <Empty>{t("personal.community.noPlan")}</Empty>
            <Button variant="outline" size="sm" asChild>
              <Link href="/personal/fire">{t("personal.sections.fire")}</Link>
            </Button>
          </div>
        </Panel>
      ) : (
        <>
          <Panel
            title={
              result.data.age_band
                ? t("personal.community.band", {
                    from: f.num(result.data.age_band[0], 0),
                    to: f.num(result.data.age_band[1], 0),
                  })
                : t("personal.community.noBand")
            }
          >
            <StatGrid>
              <Stat label={t("personal.community.yourSavingsRate")} value={f.pct(result.data.you?.savings_rate_pct, 1)} />
              <Stat label={t("personal.community.yourProgress")} value={f.pct(result.data.you?.fire_progress_pct, 1)} />
              {result.data.group && (
                <>
                  <Stat label={t("personal.community.medianSavingsRate")} value={f.pct(result.data.group.median_savings_rate_pct, 1)} />
                  <Stat
                    label={t("personal.community.medianProgress")}
                    value={f.pct(result.data.group.median_fire_progress_pct, 1)}
                    hint={t("personal.community.groupSize", { n: f.num(result.data.group.size_at_least, 0) })}
                  />
                </>
              )}
            </StatGrid>
          </Panel>
          {!result.data.group_size_met && (
            <Empty>{t("personal.community.tooSmall", { n: f.num(result.data.min_group_size, 0) })}</Empty>
          )}
        </>
      )}
    </PersonalShell>
  );
}
