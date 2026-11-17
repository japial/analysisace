import {
  type AltAssetDetail,
  CASH_FLOW_TYPES,
  type DueDiligence,
  type Envelope,
  LIQUIDITY_LEVELS,
  type Member,
  SHARIAH_FLAGS,
} from "@analysisace/core";
import { Download } from "lucide-react";
import { notFound } from "next/navigation";

import {
  addCashFlowAction,
  addValuationAction,
  deleteAltAssetAction,
  deleteCashFlowAction,
  deleteDocumentAction,
  deleteValuationAction,
  setOwnersAction,
  updateAltAssetAction,
  uploadDocumentAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, Facts, Panel, ShariahBadge, Stat, StatGrid } from "@/components/personal/display";
import { DueDiligenceFields } from "@/components/personal/due-diligence";
import {
  ActionForm,
  CheckField,
  DeleteButton,
  FieldGrid,
  FileField,
  OwnersEditor,
  SelectField,
  TextareaField,
} from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { downloadHref } from "@/lib/download";
import { hh, load } from "@/lib/personal";
import {
  type PageProps,
  enumLabel,
  enumOptions,
  memberOptions,
  setup,
  todayDhaka,
} from "@/lib/personal-page";

const DOCUMENT_TYPES = ["DEED", "AGREEMENT", "RECEIPT", "OTHER"] as const;

/** One alternative investment: values, cash flows, documents and owners (F25). */
export default async function AltAssetPage({ params }: PageProps<{ id: string }>) {
  const { locale, id } = await params;
  const { ctx, t, f } = await setup(locale, `/personal/assets/${id}`);
  const trail = [{ label: t("personal.sections.assets"), href: "/personal/assets" }];
  if (!ctx.household) return <PersonalShell ctx={ctx} title={t("personal.sections.assets")}>{null}</PersonalShell>;

  let detail: Envelope<AltAssetDetail>;
  try {
    detail = await hh<Envelope<AltAssetDetail>>(ctx, `/alt-assets/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const [dd, members] = await Promise.all([
    load(hh<Envelope<DueDiligence>>(ctx, "/alt-assets/due-diligence")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const hid = ctx.household.id;
  const { asset, valuations, cash_flows: flows, documents } = detail.data;
  const checklist = dd.ok ? dd.data.data.checklist : [];
  const people = members.ok ? memberOptions(members.data) : [];
  const memberName = (mid: string | null) =>
    (members.ok && members.data.find((m) => m.id === mid)?.display_name) || "—";
  const footnote = { asOf: detail.as_of, sources: detail.sources };

  return (
    <PersonalShell
      ctx={ctx}
      title={asset.name}
      trail={trail}
      actions={
        ctx.canEdit && (
          <DeleteButton
            action={deleteAltAssetAction.bind(null, hid, id)}
            label={t("personal.assets.delete")}
            title={t("personal.assets.delete")}
            body={t("personal.assets.deleteBody")}
            iconOnly={false}
          />
        )
      }
    >
      <StatGrid>
        <Stat label={t("personal.value")} value={f.bdt(asset.value)} hint={`${enumLabel(t, "valueMethod", asset.value_method)} · ${f.date(asset.valued_on)}`} />
        <Stat label={t("personal.assets.householdPart")} value={f.bdt(asset.household_value)} hint={f.pct(asset.household_pct, 0)} />
        <Stat label={t("personal.assets.cashReceived")} value={f.bdt(asset.cash_received)} />
        <Stat label={t("personal.assets.xirr")} value={f.pct(asset.xirr_pct, 2, true)} hint={t("personal.assets.xirrHint")} />
      </StatGrid>

      <Panel title={t("personal.details")} footnote={footnote}>
        <Facts
          items={[
            { label: t("personal.type"), value: enumLabel(t, "altAsset", asset.type) },
            { label: t("personal.cost"), value: f.bdt(asset.cost) },
            { label: t("personal.assets.purchaseDate"), value: f.date(asset.purchase_date) },
            { label: t("personal.assets.liquidity"), value: enumLabel(t, "liquidity", asset.liquidity) },
            { label: t("personal.assets.counterparty"), value: asset.counterparty ?? "—" },
            { label: t("personal.assets.exitDate"), value: f.date(asset.expected_exit_date) },
            { label: t("personal.shariah"), value: <ShariahBadge status={asset.shariah_flag} /> },
            { label: t("personal.assets.revaluationNext"), value: f.date(asset.revaluation_due) },
            ...(asset.weight_grams
              ? [{ label: t("personal.assets.weight"), value: `${f.num(asset.weight_grams, 4)} g · ${asset.karat ?? "—"}K` }]
              : []),
          ]}
        />
        {asset.notes && <p className="mt-4 text-sm whitespace-pre-line text-secondary-foreground">{asset.notes}</p>}
      </Panel>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.assets.valuations")} description={t("personal.assets.valuationsIntro")}>
          <div className="flex flex-col gap-4">
            {valuations.length === 0 ? (
              <Empty>{t("personal.assets.noValuations")}</Empty>
            ) : (
              <ul className="flex flex-col divide-y divide-border text-sm">
                {valuations.map((v) => (
                  <li key={v.id} className="flex items-center justify-between gap-3 py-2">
                    <span>{f.date(v.date)}</span>
                    <span className="flex items-center gap-2">
                      <span className="tabular-nums text-mono">{f.bdt(v.value)}</span>
                      {ctx.canEdit && (
                        <DeleteButton action={deleteValuationAction.bind(null, hid, id, v.id)} label={t("personal.assets.deleteValuation")} title={t("personal.assets.deleteValuation")} />
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {ctx.canEdit && (
              <ActionForm action={addValuationAction.bind(null, hid, id)} submitLabel={t("personal.assets.addValuation")} success={t("common.saved")}>
                <FieldGrid className="lg:grid-cols-2">
                  <Field label={t("personal.date")} name="date" id="val-date" type="date" defaultValue={todayDhaka()} required />
                  <Field label={t("personal.value")} name="value" id="val-value" type="number" inputMode="decimal" min="0" step="0.01" required />
                </FieldGrid>
              </ActionForm>
            )}
          </div>
        </Panel>

        <Panel title={t("personal.assets.cashFlows")} description={t("personal.assets.cashFlowsIntro")}>
          <div className="flex flex-col gap-4">
            {flows.length === 0 ? (
              <Empty>{t("personal.assets.noCashFlows")}</Empty>
            ) : (
              <ul className="flex flex-col divide-y divide-border text-sm">
                {flows.map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-3 py-2">
                    <span>
                      {f.date(c.date)} · {enumLabel(t, "cashFlow", c.type)}
                      {c.note && <span className="block text-xs text-muted-foreground">{c.note}</span>}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="tabular-nums text-mono">{f.bdt(c.amount)}</span>
                      {ctx.canEdit && (
                        <DeleteButton action={deleteCashFlowAction.bind(null, hid, id, c.id)} label={t("personal.assets.deleteCashFlow")} title={t("personal.assets.deleteCashFlow")} />
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {ctx.canEdit && (
              <ActionForm action={addCashFlowAction.bind(null, hid, id)} submitLabel={t("personal.assets.addCashFlow")} success={t("common.saved")}>
                <FieldGrid className="lg:grid-cols-2">
                  <Field label={t("personal.date")} name="date" id="cf-date" type="date" defaultValue={todayDhaka()} required />
                  <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "cashFlow", CASH_FLOW_TYPES)} defaultValue="RENT" />
                  <SelectField label={t("personal.assets.direction")} name="direction" options={[{ value: "IN", label: t("personal.assets.received") }, { value: "OUT", label: t("personal.assets.paidIn") }]} defaultValue="IN" />
                  <Field label={t("personal.amount")} name="amount" id="cf-amount" type="number" inputMode="decimal" min="0.01" step="0.01" required />
                  <Field label={t("personal.note")} name="note" id="cf-note" maxLength={300} />
                </FieldGrid>
              </ActionForm>
            )}
          </div>
        </Panel>
      </div>

      <Panel title={t("personal.assets.documents")} description={t("personal.assets.documentsIntro")} table>
        {documents.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.assets.noDocuments")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.assets.file")}</TableHead>
                <TableHead className="hidden sm:table-cell">{t("personal.type")}</TableHead>
                <TableHead className="hidden sm:table-cell">{t("personal.date")}</TableHead>
                <TableHead className="w-24"><span className="sr-only">{t("personal.actions")}</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell lang="en">{doc.filename}</TableCell>
                  <TableCell className="hidden sm:table-cell">{enumLabel(t, "documentType", doc.type)}</TableCell>
                  <TableCell className="hidden sm:table-cell">{f.date(doc.created_at)}</TableCell>
                  <TableCell>
                    <span className="flex items-center gap-1">
                      <Button variant="ghost" mode="icon" size="sm" asChild>
                        <a href={downloadHref(locale, `/households/${hid}/alt-assets/${id}/documents/${doc.id}`)} download aria-label={t("personal.assets.download", { name: doc.filename })}>
                          <Download />
                        </a>
                      </Button>
                      {ctx.canEdit && (
                        <DeleteButton action={deleteDocumentAction.bind(null, hid, id, doc.id)} label={t("personal.assets.deleteDocument")} title={t("personal.assets.deleteDocument")} />
                      )}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {ctx.canEdit && (
          <div className="border-t border-border p-5">
            <ActionForm action={uploadDocumentAction.bind(null, hid, id)} submitLabel={t("personal.assets.upload")} success={t("common.saved")}>
              <FieldGrid className="lg:grid-cols-2">
                <FileField label={t("personal.assets.file")} name="file" required hint={t("personal.assets.fileHint")} />
                <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "documentType", DOCUMENT_TYPES)} defaultValue="DEED" />
              </FieldGrid>
            </ActionForm>
          </div>
        )}
      </Panel>

      {ctx.canEdit && (
        <Panel title={t("personal.edit")}>
          <ActionForm action={updateAltAssetAction.bind(null, hid, id, checklist)} submitLabel={t("common.save")} success={t("common.saved")} reset={false}>
            <FieldGrid>
              <Field label={t("personal.name")} name="name" defaultValue={asset.name} maxLength={200} required />
              <Field label={t("personal.assets.purchaseDate")} name="purchase_date" type="date" defaultValue={asset.purchase_date ?? ""} />
              <Field label={t("personal.cost")} name="cost" type="number" inputMode="decimal" min="0" step="0.01" defaultValue={asset.cost} />
              <SelectField label={t("personal.assets.liquidity")} name="liquidity" options={enumOptions(t, "liquidity", LIQUIDITY_LEVELS)} defaultValue={asset.liquidity} />
              <Field label={t("personal.assets.counterparty")} name="counterparty" defaultValue={asset.counterparty ?? ""} maxLength={200} />
              <Field label={t("personal.assets.exitDate")} name="expected_exit_date" type="date" defaultValue={asset.expected_exit_date ?? ""} />
              <Field label={t("personal.assets.weight")} name="weight_grams" type="number" inputMode="decimal" min="0.0001" step="0.0001" defaultValue={asset.weight_grams ?? ""} />
              <Field label={t("personal.assets.karat")} name="karat" type="number" min="1" max="24" defaultValue={asset.karat ?? ""} />
              <SelectField label={t("personal.shariah")} name="shariah_flag" options={enumOptions(t, "shariah", SHARIAH_FLAGS)} defaultValue={asset.shariah_flag} />
            </FieldGrid>
            <CheckField label={t("personal.assets.recoverable")} name="is_recoverable" defaultChecked={asset.is_recoverable} hint={t("personal.assets.recoverableHint")} />
            <TextareaField label={t("personal.assets.notes")} name="notes" rows={3} maxLength={2000} defaultValue={asset.notes ?? ""} />
            {checklist.length > 0 && <DueDiligenceFields checklist={checklist} answers={asset.due_diligence} />}
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.owners.title")}>
        <div className="flex flex-col gap-4">
          <ul className="text-sm">
            {asset.owners.map((o, i) => (
              <li key={i}>
                {o.member_id ? memberName(o.member_id) : o.external_name} · {f.pct(o.pct, 2)}
              </li>
            ))}
          </ul>
          {ctx.canEdit && (
            <ActionForm action={setOwnersAction.bind(null, hid, "ALT_ASSET", id)} submitLabel={t("personal.owners.save")} success={t("common.saved")} reset={false}>
              <OwnersEditor
                members={people}
                initial={asset.owners.map((o) => ({ member: o.member_id ?? "EXTERNAL", external: o.external_name ?? "", pct: o.pct }))}
              />
            </ActionForm>
          )}
        </div>
      </Panel>
    </PersonalShell>
  );
}
