import {
  ALT_ASSET_TYPES,
  type AltAssetView,
  type DueDiligence,
  type Envelope,
  LIQUIDITY_LEVELS,
  type Member,
  SHARIAH_FLAGS,
} from "@analysisace/core";
import { CalendarClock } from "lucide-react";

import { addAltAssetAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, ShariahBadge, Stat, StatGrid } from "@/components/personal/display";
import {
  ActionForm,
  CheckField,
  FieldGrid,
  OwnersEditor,
  SelectField,
  TextareaField,
} from "@/components/personal/forms";
import { DueDiligenceFields } from "@/components/personal/due-diligence";
import { PersonalShell } from "@/components/personal/shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import {
  type PageProps,
  enumLabel,
  enumOptions,
  memberOptions,
  sectionMetadata,
  setup,
} from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("assets");

/** Property, gold, business stakes, private loans and other assets (F25). */
export default async function AssetsPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/assets");
  const title = t("personal.sections.assets");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [assets, dd, members] = await Promise.all([
    load(hh<Envelope<AltAssetView[]>>(ctx, "/alt-assets")),
    load(hh<Envelope<DueDiligence>>(ctx, "/alt-assets/due-diligence")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const people = members.ok ? memberOptions(members.data) : [];
  const checklist = dd.ok ? dd.data.data.checklist : [];

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.assets.intro")}>
      {!assets.ok ? (
        <LoadError code={assets.code} />
      ) : (
        <Panel
          title={t("personal.assets.listTitle")}
          table
          footnote={{ asOf: assets.data.as_of, sources: assets.data.sources }}
        >
          {assets.data.data.length === 0 ? (
            <div className="p-5"><Empty>{t("personal.assets.empty")}</Empty></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.name")}</TableHead>
                  <TableHead className="text-end">{t("personal.value")}</TableHead>
                  <TableHead className="hidden text-end md:table-cell">{t("personal.assets.xirr")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("personal.assets.liquidity")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("personal.shariah")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assets.data.data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Link href={`/personal/assets/${a.id}`} className="text-primary hover:underline">
                        {a.name}
                      </Link>
                      <span className="block text-xs text-muted-foreground">
                        {enumLabel(t, "altAsset", a.type)} · {enumLabel(t, "valueMethod", a.value_method)}
                        {a.valued_on ? ` · ${f.date(a.valued_on)}` : ""}
                      </span>
                      {a.revaluation_due && (
                        <span className="mt-0.5 flex items-center gap-1 text-xs text-destructive">
                          <CalendarClock className="size-3.5" aria-hidden="true" />
                          {t("personal.assets.revaluationDue", { date: f.date(a.revaluation_due) })}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-end tabular-nums">
                      {f.bdt(a.household_value)}
                      {a.household_pct !== "100" && (
                        <span className="block text-xs text-muted-foreground">
                          {t("personal.portfolio.householdShare", { pct: f.pct(a.household_pct, 0) })}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden text-end tabular-nums md:table-cell">{f.pct(a.xirr_pct, 2, true)}</TableCell>
                    <TableCell className="hidden lg:table-cell">{enumLabel(t, "liquidity", a.liquidity)}</TableCell>
                    <TableCell className="hidden lg:table-cell"><ShariahBadge status={a.shariah_flag} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>
      )}

      {dd.ok && (
        <StatGrid>
          <Stat
            label={t("personal.assets.tbill")}
            value={f.pct(dd.data.data.tbill_yield_pct)}
            hint={t("personal.assets.tbillHint", { date: f.date(dd.data.data.tbill_date) })}
          />
        </StatGrid>
      )}

      {ctx.canEdit && (
        <Panel title={t("personal.assets.addTitle")} description={t("personal.assets.addIntro")}>
          <ActionForm action={addAltAssetAction.bind(null, ctx.household.id, checklist)} submitLabel={t("personal.assets.add")}>
            <FieldGrid>
              <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "altAsset", ALT_ASSET_TYPES)} defaultValue="LAND" />
              <Field label={t("personal.name")} name="name" maxLength={200} required />
              <Field label={t("personal.assets.purchaseDate")} name="purchase_date" type="date" />
              <Field label={t("personal.cost")} name="cost" type="number" inputMode="decimal" min="0" step="0.01" required />
              <Field label={t("personal.assets.currentValue")} name="current_value" type="number" inputMode="decimal" min="0" step="0.01" hint={t("personal.assets.currentValueHint")} />
              <SelectField label={t("personal.assets.liquidity")} name="liquidity" options={enumOptions(t, "liquidity", LIQUIDITY_LEVELS)} defaultValue=">1Y" />
              <Field label={t("personal.assets.counterparty")} name="counterparty" maxLength={200} />
              <Field label={t("personal.assets.exitDate")} name="expected_exit_date" type="date" />
              <SelectField label={t("personal.assets.revalueEvery")} name="revaluation_months" options={[{ value: "6", label: t("personal.assets.months", { n: 6 }) }, { value: "12", label: t("personal.assets.months", { n: 12 }) }]} defaultValue="12" />
              <Field label={t("personal.assets.weight")} name="weight_grams" type="number" inputMode="decimal" min="0.0001" step="0.0001" hint={t("personal.assets.weightHint")} />
              <Field label={t("personal.assets.karat")} name="karat" type="number" min="1" max="24" step="1" />
              <SelectField label={t("personal.shariah")} name="shariah_flag" options={enumOptions(t, "shariah", SHARIAH_FLAGS)} defaultValue="UNKNOWN" />
            </FieldGrid>
            <CheckField label={t("personal.assets.recoverable")} name="is_recoverable" defaultChecked hint={t("personal.assets.recoverableHint")} />
            <TextareaField label={t("personal.assets.notes")} name="notes" rows={3} maxLength={2000} className="[&_textarea]:font-sans [&_textarea]:text-sm" />
            {checklist.length > 0 && <DueDiligenceFields checklist={checklist} />}
            <OwnersEditor members={people} />
          </ActionForm>
        </Panel>
      )}
    </PersonalShell>
  );
}
