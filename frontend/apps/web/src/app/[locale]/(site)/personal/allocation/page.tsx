import type { Allocation, Envelope } from "@analysisace/core";
import { TriangleAlert } from "lucide-react";

import { setTargetsAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, ShareBars } from "@/components/personal/display";
import { ActionForm } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("allocation");

/** Allocation by class, sector, holding and Shariah status, and drift from target (F16). */
export default async function AllocationPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/allocation");
  const title = t("personal.sections.allocation");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const result = await load(hh<Envelope<Allocation>>(ctx, "/portfolio/allocation"));
  if (!result.ok) {
    return (
      <PersonalShell ctx={ctx} title={title}>
        <LoadError code={result.code} />
      </PersonalShell>
    );
  }
  const d = result.data.data;
  const footnote = { asOf: result.data.as_of, sources: result.data.sources };
  const bars = (rows: Allocation["by_class"], group?: string) =>
    rows.map((row) => ({
      key: row.key,
      label: row.name ?? (group ? enumLabel(t, group, row.key) : row.key),
      value: f.compact(row.value),
      pct: row.pct,
      pctText: f.pct(row.pct, 1),
    }));
  const hasTargets = d.drift.some((row) => row.target_pct !== "0");

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.allocation.intro")}>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.allocation.byClass")} footnote={footnote}>
          {d.by_class.length === 0 ? <Empty>{t("personal.overview.empty")}</Empty> : <ShareBars rows={bars(d.by_class, "assetClass")} />}
        </Panel>
        <Panel title={t("personal.allocation.byShariah")} description={t("personal.allocation.byShariahHint")}>
          {d.by_shariah.length === 0 ? <Empty>{t("personal.overview.empty")}</Empty> : <ShareBars rows={bars(d.by_shariah, "shariah")} />}
        </Panel>
        <Panel title={t("personal.allocation.bySector")} description={t("personal.allocation.bySectorHint")}>
          {d.by_sector.length === 0 ? <Empty>{t("personal.allocation.noSectors")}</Empty> : <ShareBars rows={bars(d.by_sector)} />}
        </Panel>
        <Panel title={t("personal.allocation.byHolding")}>
          {d.by_holding.length === 0 ? <Empty>{t("personal.overview.empty")}</Empty> : <ShareBars rows={bars(d.by_holding.slice(0, 10))} />}
        </Panel>
      </div>

      <Panel title={t("personal.allocation.driftTitle")} description={t("personal.allocation.driftIntro")} table>
        {!hasTargets ? (
          <div className="p-5"><Empty>{t("personal.allocation.noTargets")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.allocation.assetClass")}</TableHead>
                <TableHead className="text-end">{t("personal.allocation.actual")}</TableHead>
                <TableHead className="text-end">{t("personal.allocation.target")}</TableHead>
                <TableHead className="text-end">{t("personal.allocation.drift")}</TableHead>
                <TableHead className="hidden text-end md:table-cell">{t("personal.allocation.difference")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.drift.map((row) => (
                <TableRow key={row.asset_class}>
                  <TableCell>{enumLabel(t, "assetClass", row.asset_class)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.pct(row.actual_pct, 1)}</TableCell>
                  <TableCell className="text-end tabular-nums">
                    {f.pct(row.target_pct, 1)}
                    <span className="block text-xs text-muted-foreground">± {f.num(row.band_pct, 1)}</span>
                  </TableCell>
                  <TableCell className="text-end tabular-nums">
                    <span className="inline-flex items-center gap-1">
                      {row.outside_band && <TriangleAlert className="size-3.5 text-destructive" aria-hidden="true" />}
                      {t("personal.allocation.points", { value: f.num(row.drift_pts, 2) })}
                    </span>
                    {row.outside_band && <span className="block text-xs text-destructive">{t("personal.allocation.outsideBand")}</span>}
                  </TableCell>
                  <TableCell className="hidden text-end tabular-nums md:table-cell">{f.bdt(row.difference)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>

      {ctx.canEdit && (
        <Panel title={t("personal.allocation.setTargets")} description={t("personal.allocation.setTargetsIntro")}>
          <ActionForm
            action={setTargetsAction.bind(null, ctx.household.id, d.asset_classes)}
            submitLabel={t("common.save")}
            success={t("common.saved")}
            reset={false}
          >
            <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
              {d.asset_classes.map((cls) => {
                const current = d.drift.find((row) => row.asset_class === cls);
                return (
                  <fieldset key={cls} className="grid grid-cols-2 gap-3">
                    <legend className="col-span-2 mb-1 text-sm font-medium text-mono">{enumLabel(t, "assetClass", cls)}</legend>
                    <Field
                      label={t("personal.allocation.targetPct")}
                      name={`target_${cls}`}
                      id={`target_${cls}`}
                      type="number"
                      inputMode="decimal"
                      min="0"
                      max="100"
                      step="0.1"
                      defaultValue={current && current.target_pct !== "0" ? current.target_pct : ""}
                    />
                    <Field
                      label={t("personal.allocation.bandPct")}
                      name={`band_${cls}`}
                      id={`band_${cls}`}
                      type="number"
                      inputMode="decimal"
                      min="0"
                      max="50"
                      step="0.1"
                      defaultValue={current && current.band_pct !== "0" ? current.band_pct : "5"}
                    />
                  </fieldset>
                );
              })}
            </div>
          </ActionForm>
        </Panel>
      )}
    </PersonalShell>
  );
}
