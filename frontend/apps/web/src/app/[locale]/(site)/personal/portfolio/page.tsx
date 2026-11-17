import {
  ACCOUNT_TYPES,
  type Account,
  type Envelope,
  INSTRUMENT_TYPES,
  LIABILITY_TYPES,
  type Member,
  PAYMENT_FREQUENCIES,
  type PortfolioSummary,
} from "@analysisace/core";

import {
  addAccountAction,
  addHoldingAction,
  addLiabilityAction,
  deleteAccountAction,
  deleteLiabilityAction,
  importBrokerAction,
  updateLiabilityAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, ShariahBadge, Stat, StatGrid } from "@/components/personal/display";
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

export const generateMetadata = sectionMetadata("portfolio");

/** Accounts, holdings and debts, valued today (F14, FR14.1 to FR14.5). */
export default async function PortfolioPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/portfolio");
  const title = t("personal.sections.portfolio");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [accounts, summary, members] = await Promise.all([
    load(hh<Account[]>(ctx, "/accounts")),
    load(hh<Envelope<PortfolioSummary>>(ctx, "/portfolio/summary")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const hid = ctx.household.id;
  const people = members.ok ? memberOptions(members.data) : [];
  const accountOptions = accounts.ok
    ? accounts.data.map((a) => ({ value: a.id, label: `${a.institution} · ${a.name}` }))
    : [];
  const positions = summary.ok ? summary.data.data.positions.filter((p) => p.kind === "HOLDING") : [];

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.portfolio.intro")}>
      {summary.ok ? (
        <StatGrid>
          <Stat label={t("personal.overview.assets")} value={f.compact(summary.data.data.assets)} hint={f.bdt(summary.data.data.assets)} />
          <Stat label={t("personal.overview.liabilities")} value={f.compact(summary.data.data.liabilities)} hint={f.bdt(summary.data.data.liabilities)} />
          <Stat label={t("personal.overview.netWorth")} value={f.compact(summary.data.data.net_worth)} hint={f.bdt(summary.data.data.net_worth)} />
          <Stat label={t("personal.portfolio.valuedOn")} value={f.date(summary.data.data.as_of_date)} />
        </StatGrid>
      ) : (
        <LoadError code={summary.code} />
      )}

      {!accounts.ok ? (
        <LoadError code={accounts.code} />
      ) : accounts.data.length === 0 ? (
        <Panel title={t("personal.portfolio.accounts")}>
          <Empty>{t("personal.portfolio.noAccounts")}</Empty>
        </Panel>
      ) : (
        accounts.data.map((account) => {
          const rows = positions.filter((p) => p.account_id === account.id);
          return (
            <Panel
              key={account.id}
              title={`${account.institution} · ${account.name}`}
              description={[enumLabel(t, "accountType", account.type), account.masked_number].filter(Boolean).join(" · ")}
              actions={
                ctx.canEdit && (
                  <DeleteButton
                    action={deleteAccountAction.bind(null, hid, account.id)}
                    label={t("personal.portfolio.deleteAccount")}
                    title={t("personal.portfolio.deleteAccount")}
                    body={t("personal.portfolio.deleteAccountBody")}
                  />
                )
              }
              table
              footnote={summary.ok ? { asOf: summary.data.as_of, sources: summary.data.sources } : undefined}
            >
              {rows.length === 0 ? (
                <div className="p-5"><Empty>{t("personal.portfolio.noHoldings")}</Empty></div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("personal.name")}</TableHead>
                      <TableHead className="hidden md:table-cell">{t("personal.portfolio.quantity")}</TableHead>
                      <TableHead className="hidden sm:table-cell text-end">{t("personal.cost")}</TableHead>
                      <TableHead className="text-end">{t("personal.value")}</TableHead>
                      <TableHead className="hidden lg:table-cell">{t("personal.shariah")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell>
                          <Link href={`/personal/portfolio/holdings/${p.id}`} className="text-primary hover:underline" lang={p.ticker ? "en" : undefined}>
                            {p.name}
                          </Link>
                          <span className="block text-xs text-muted-foreground">
                            {enumLabel(t, "instrument", p.type)} · {enumLabel(t, "valueMethod", p.method)}
                          </span>
                        </TableCell>
                        <TableCell className="hidden tabular-nums md:table-cell">{f.num(p.quantity, 4)}</TableCell>
                        <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.bdt(p.cost)}</TableCell>
                        <TableCell className="text-end tabular-nums">
                          {f.bdt(p.household_value)}
                          {p.household_pct !== "100" && (
                            <span className="block text-xs text-muted-foreground">
                              {t("personal.portfolio.householdShare", { pct: f.pct(p.household_pct, 0) })}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell"><ShariahBadge status={p.shariah} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Panel>
          );
        })
      )}

      {ctx.canEdit && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2 xl:gap-7.5">
          <Panel title={t("personal.portfolio.addAccount")} description={t("personal.portfolio.addAccountIntro")}>
            <ActionForm action={addAccountAction.bind(null, hid)} submitLabel={t("personal.portfolio.addAccount")} success={t("common.saved")}>
              <FieldGrid className="lg:grid-cols-2">
                <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "accountType", ACCOUNT_TYPES)} defaultValue="BO" />
                <Field label={t("personal.portfolio.institution")} name="institution" maxLength={200} required />
                <Field label={t("personal.name")} name="name" maxLength={120} required />
                <Field label={t("personal.portfolio.number")} name="number" maxLength={40} hint={t("personal.portfolio.numberHint")} autoComplete="off" />
              </FieldGrid>
            </ActionForm>
          </Panel>

          {accountOptions.length > 0 && (
            <Panel title={t("personal.portfolio.importTitle")} description={t("personal.portfolio.importIntro")}>
              <ActionForm action={importBrokerAction.bind(null, hid)} submitLabel={t("personal.import.submit")}>
                <SelectField
                  label={t("personal.portfolio.account")}
                  name="account_id"
                  options={accounts.ok ? accounts.data.filter((a) => a.type === "BO").map((a) => ({ value: a.id, label: `${a.institution} · ${a.name}` })) : []}
                  required
                />
                <FileField label={t("personal.import.file")} name="file" accept=".csv,text/csv" />
                <TextareaField label={t("personal.import.paste")} name="csv" rows={3} />
              </ActionForm>
            </Panel>
          )}
        </div>
      )}

      {ctx.canEdit && accountOptions.length > 0 && (
        <Panel title={t("personal.portfolio.addHolding")} description={t("personal.portfolio.addHoldingIntro")}>
          <ActionForm action={addHoldingAction.bind(null, hid)} submitLabel={t("personal.portfolio.addHolding")} success={t("common.saved")}>
            <FieldGrid>
              <SelectField label={t("personal.portfolio.account")} name="account_id" options={accountOptions} />
              <SelectField label={t("personal.type")} name="instrument_type" options={enumOptions(t, "instrument", INSTRUMENT_TYPES)} defaultValue="DSE_SHARE" />
              <Field label={t("personal.name")} name="name" maxLength={200} required />
              <Field label={t("personal.portfolio.ticker")} name="ticker" maxLength={20} lang="en" hint={t("personal.portfolio.tickerHint")} />
              <Field label={t("personal.portfolio.quantity")} name="quantity" type="number" inputMode="decimal" min="0.0001" step="0.0001" defaultValue="1" />
              <Field label={t("personal.portfolio.totalCost")} name="cost" type="number" inputMode="decimal" min="0" step="0.01" required />
              <Field label={t("personal.portfolio.currentValue")} name="manual_value" type="number" inputMode="decimal" min="0" step="0.01" hint={t("personal.portfolio.currentValueHint")} />
              <Field label={t("personal.startDate")} name="start_date" type="date" />
              <Field label={t("personal.portfolio.maturity")} name="maturity_date" type="date" />
              <Field label={t("personal.portfolio.expectedRate")} name="expected_rate" type="number" inputMode="decimal" step="0.01" />
              <SelectField label={t("personal.portfolio.paymentFrequency")} name="payment_frequency" options={enumOptions(t, "frequency", PAYMENT_FREQUENCIES)} placeholder={t("personal.notSet")} />
            </FieldGrid>
            <CheckField label={t("personal.portfolio.interestBearing")} name="is_interest_bearing" hint={t("personal.portfolio.interestBearingHint")} />
            <OwnersEditor members={people} />
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.portfolio.liabilities")} description={t("personal.portfolio.liabilitiesIntro")}>
        <div className="flex flex-col gap-5">
          {!summary.ok ? null : summary.data.data.debts.length === 0 ? (
            <Empty>{t("personal.portfolio.noLiabilities")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {summary.data.data.debts.map((d) => (
                <li key={d.id} className="flex flex-col gap-2 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm">
                      <p className="text-mono">{d.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {enumLabel(t, "liabilityType", d.type)}
                        {d.lender ? ` · ${d.lender}` : ""}
                        {d.is_interest_bearing ? ` · ${t("personal.portfolio.interestBearing")}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <div className="text-end">
                        <p className="tabular-nums text-mono">{f.bdt(d.household_outstanding)}</p>
                        <p className="text-xs text-muted-foreground">
                          {t("personal.portfolio.dueWithinYear", { amount: f.bdt(d.due_within_year) })}
                        </p>
                      </div>
                      {ctx.canEdit && (
                        <DeleteButton action={deleteLiabilityAction.bind(null, hid, d.id)} label={t("personal.portfolio.deleteLiability")} title={t("personal.portfolio.deleteLiability")} />
                      )}
                    </div>
                  </div>
                  {ctx.canEdit && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-secondary-foreground hover:text-mono">{t("personal.portfolio.updateBalance")}</summary>
                      <ActionForm action={updateLiabilityAction.bind(null, hid, d.id)} submitLabel={t("common.save")} success={t("common.saved")} reset={false} className="mt-3">
                        <FieldGrid>
                          <Field label={t("personal.portfolio.outstanding")} name="outstanding" id={`out-${d.id}`} type="number" inputMode="decimal" min="0" step="0.01" defaultValue={d.outstanding} />
                          <Field label={t("personal.portfolio.dueWithinYearLabel")} name="due_within_year" id={`due-${d.id}`} type="number" inputMode="decimal" min="0" step="0.01" defaultValue={d.due_within_year} />
                        </FieldGrid>
                      </ActionForm>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          )}
          {ctx.canEdit && (
            <details>
              <summary className="cursor-pointer text-sm font-medium text-primary">{t("personal.portfolio.addLiability")}</summary>
              <ActionForm action={addLiabilityAction.bind(null, hid)} submitLabel={t("personal.portfolio.addLiability")} success={t("common.saved")} className="mt-4">
                <FieldGrid>
                  <SelectField label={t("personal.type")} name="type" options={enumOptions(t, "liabilityType", LIABILITY_TYPES)} defaultValue="HOME_LOAN" />
                  <Field label={t("personal.name")} name="name" maxLength={200} required />
                  <Field label={t("personal.portfolio.lender")} name="lender" maxLength={200} />
                  <Field label={t("personal.portfolio.outstanding")} name="outstanding" type="number" inputMode="decimal" min="0" step="0.01" required />
                  <Field label={t("personal.portfolio.dueWithinYearLabel")} name="due_within_year" type="number" inputMode="decimal" min="0" step="0.01" hint={t("personal.portfolio.dueWithinYearHint")} />
                  <Field label={t("personal.endDate")} name="end_date" type="date" />
                </FieldGrid>
                <CheckField label={t("personal.portfolio.interestBearing")} name="is_interest_bearing" />
                <OwnersEditor members={people} />
              </ActionForm>
            </details>
          )}
        </div>
      </Panel>
    </PersonalShell>
  );
}
