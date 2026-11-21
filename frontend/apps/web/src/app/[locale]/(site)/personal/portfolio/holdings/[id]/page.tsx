import {
  type Account,
  type Holding,
  type Member,
  type OwnerShare,
  PAYMENT_FREQUENCIES,
  TRANSACTION_TYPES,
  type Transaction,
} from "@analysisace/core";
import { notFound } from "next/navigation";

import {
  addTransactionAction,
  deleteHoldingAction,
  deleteTransactionAction,
  setOwnersAction,
  updateHoldingAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, Facts, Panel } from "@/components/personal/display";
import {
  ActionForm,
  CheckField,
  DeleteButton,
  FieldGrid,
  OwnersEditor,
  SelectField,
} from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { hh, load } from "@/lib/personal";
import {
  type PageProps,
  enumLabel,
  enumOptions,
  memberOptions,
  setup,
  todayDhaka,
} from "@/lib/personal-page";

/** One holding: its details, transactions and owners (FR14.1, FR15.1, FR24.3, FR26.6). */
export default async function HoldingPage({ params }: PageProps<{ id: string }>) {
  const { locale, id } = await params;
  const { ctx, t, f } = await setup(locale, `/personal/portfolio/holdings/${id}`);
  const crumbs = [{ label: t("personal.sections.portfolio"), href: "/personal/portfolio" }];
  if (!ctx.household) return <PersonalShell ctx={ctx} title={t("personal.sections.portfolio")}>{null}</PersonalShell>;

  let holding: Holding;
  try {
    holding = await hh<Holding>(ctx, `/holdings/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const [transactions, owners, members, accounts] = await Promise.all([
    load(hh<Transaction[]>(ctx, `/holdings/${id}/transactions`)),
    load(hh<OwnerShare[]>(ctx, `/owners/HOLDING/${id}`)),
    load(hh<Member[]>(ctx, "/members")),
    load(hh<Account[]>(ctx, "/accounts")),
  ]);
  const hid = ctx.household.id;
  const account = accounts.ok ? accounts.data.find((a) => a.id === holding.account_id) : undefined;
  const people = members.ok ? memberOptions(members.data) : [];
  const memberName = (mid: string | null) =>
    (members.ok && members.data.find((m) => m.id === mid)?.display_name) || "—";

  return (
    <PersonalShell
      ctx={ctx}
      title={holding.name}
      trail={crumbs}
      actions={
        ctx.canEdit && (
          <DeleteButton
            action={deleteHoldingAction.bind(null, hid, id)}
            label={t("personal.portfolio.deleteHolding")}
            title={t("personal.portfolio.deleteHolding")}
            iconOnly={false}
          />
        )
      }
    >
      <Panel title={t("personal.details")}>
        <Facts
          items={[
            { label: t("personal.portfolio.account"), value: account ? `${account.institution} · ${account.name}` : "—" },
            { label: t("personal.type"), value: enumLabel(t, "instrument", holding.instrument_type) },
            { label: t("personal.portfolio.ticker"), value: <span lang="en">{holding.ticker ?? "—"}</span> },
            { label: t("personal.portfolio.quantity"), value: f.num(holding.quantity, 4) },
            { label: t("personal.cost"), value: f.bdt(holding.cost) },
            { label: t("personal.portfolio.currentValue"), value: f.bdt(holding.manual_value) },
            { label: t("personal.startDate"), value: f.date(holding.start_date) },
            { label: t("personal.portfolio.maturity"), value: f.date(holding.maturity_date) },
            { label: t("personal.portfolio.expectedRate"), value: f.pct(holding.expected_rate) },
            { label: t("personal.portfolio.finalRate"), value: f.pct(holding.final_rate) },
            { label: t("personal.portfolio.profitReceived"), value: f.bdt(holding.profit_received) },
            { label: t("personal.portfolio.taxDeducted"), value: f.bdt(holding.tax_deducted) },
          ]}
        />
      </Panel>

      {ctx.canEdit && (
        <Panel title={t("personal.edit")}>
          <ActionForm action={updateHoldingAction.bind(null, hid, id)} submitLabel={t("common.save")} success={t("common.saved")} reset={false}>
            <FieldGrid>
              <Field label={t("personal.name")} name="name" defaultValue={holding.name} maxLength={200} required />
              <Field label={t("personal.portfolio.quantity")} name="quantity" type="number" inputMode="decimal" min="0.0001" step="0.0001" defaultValue={holding.quantity} />
              <Field label={t("personal.portfolio.totalCost")} name="cost" type="number" inputMode="decimal" min="0" step="0.01" defaultValue={holding.cost} />
              <Field label={t("personal.portfolio.currentValue")} name="manual_value" type="number" inputMode="decimal" min="0" step="0.01" defaultValue={holding.manual_value ?? ""} hint={t("personal.portfolio.currentValueHint")} />
              <Field label={t("personal.startDate")} name="start_date" type="date" defaultValue={holding.start_date ?? ""} />
              <Field label={t("personal.portfolio.maturity")} name="maturity_date" type="date" defaultValue={holding.maturity_date ?? ""} />
              <Field label={t("personal.portfolio.expectedRate")} name="expected_rate" type="number" inputMode="decimal" step="0.01" defaultValue={holding.expected_rate ?? ""} />
              <Field label={t("personal.portfolio.finalRate")} name="final_rate" type="number" inputMode="decimal" step="0.01" defaultValue={holding.final_rate ?? ""} hint={t("personal.portfolio.finalRateHint")} />
              <SelectField label={t("personal.portfolio.paymentFrequency")} name="payment_frequency" options={enumOptions(t, "frequency", PAYMENT_FREQUENCIES)} defaultValue={holding.payment_frequency ?? undefined} placeholder={t("personal.notSet")} />
              <Field label={t("personal.portfolio.profitReceived")} name="profit_received" type="number" inputMode="decimal" min="0" step="0.01" defaultValue={holding.profit_received} />
              <Field label={t("personal.portfolio.taxDeducted")} name="tax_deducted" type="number" inputMode="decimal" min="0" step="0.01" defaultValue={holding.tax_deducted} />
            </FieldGrid>
            <CheckField label={t("personal.portfolio.interestBearing")} name="is_interest_bearing" defaultChecked={holding.is_interest_bearing} />
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.portfolio.transactions")} description={t("personal.portfolio.transactionsIntro")}>
        <div className="flex flex-col gap-5">
          {!transactions.ok || transactions.data.length === 0 ? (
            <Empty>{t("personal.portfolio.noTransactions")}</Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.date")}</TableHead>
                  <TableHead>{t("personal.type")}</TableHead>
                  <TableHead className="text-end">{t("personal.amount")}</TableHead>
                  <TableHead className="hidden text-end sm:table-cell">{t("personal.portfolio.units")}</TableHead>
                  {ctx.canEdit && <TableHead className="w-12"><span className="sr-only">{t("personal.delete")}</span></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.data.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell className="whitespace-nowrap">{f.date(tx.date)}</TableCell>
                    <TableCell>
                      {enumLabel(t, "transaction", tx.type)}
                      {tx.note && <span className="block text-xs text-muted-foreground">{tx.note}</span>}
                    </TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(tx.amount)}</TableCell>
                    <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.num(tx.units, 4)}</TableCell>
                    {ctx.canEdit && (
                      <TableCell>
                        <DeleteButton action={deleteTransactionAction.bind(null, hid, id, tx.id)} label={t("personal.portfolio.deleteTransaction")} title={t("personal.portfolio.deleteTransaction")} />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {ctx.canEdit && (
            <ActionForm action={addTransactionAction.bind(null, hid, id)} submitLabel={t("personal.portfolio.addTransaction")} success={t("common.saved")}>
              <FieldGrid>
                <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "transaction", TRANSACTION_TYPES)} defaultValue="BUY" />
                <Field label={t("personal.date")} name="date" type="date" defaultValue={todayDhaka()} required />
                <Field label={t("personal.amount")} name="amount" type="number" inputMode="decimal" min="0" step="0.01" required />
                <Field label={t("personal.portfolio.units")} name="units" type="number" inputMode="decimal" min="0.0001" step="0.0001" hint={t("personal.portfolio.unitsHint")} />
                <Field label={t("personal.note")} name="note" maxLength={300} />
              </FieldGrid>
            </ActionForm>
          )}
        </div>
      </Panel>

      <Panel title={t("personal.owners.title")}>
        <div className="flex flex-col gap-4">
          {owners.ok && owners.data.length > 0 && (
            <ul className="text-sm">
              {owners.data.map((o, i) => (
                <li key={i}>
                  {o.member_id ? memberName(o.member_id) : o.external_name} · {f.pct(o.pct, 2)}
                </li>
              ))}
            </ul>
          )}
          {ctx.canEdit && owners.ok && (
            <ActionForm action={setOwnersAction.bind(null, hid, "HOLDING", id)} submitLabel={t("personal.owners.save")} success={t("common.saved")} reset={false}>
              <OwnersEditor
                members={people}
                initial={owners.data.map((o) => ({
                  member: o.member_id ?? "EXTERNAL",
                  external: o.external_name ?? "",
                  pct: o.pct,
                }))}
              />
            </ActionForm>
          )}
        </div>
      </Panel>
    </PersonalShell>
  );
}
