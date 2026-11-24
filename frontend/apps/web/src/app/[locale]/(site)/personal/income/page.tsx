import {
  type Envelope,
  type IncomeEntry,
  type IncomeRule,
  type IncomeSummary,
  type Member,
  type Page,
  RECURRING_FREQUENCIES,
} from "@analysisace/core";

import { Download } from "lucide-react";

import {
  addIncomeAction,
  addIncomeRuleAction,
  deleteIncomeAction,
  deleteIncomeRuleAction,
  importIncomeAction,
  setIncomeRuleActiveAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import { ActionForm, DeleteButton, FieldGrid, FileField, SelectField, TextareaField, ToggleSwitch } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { downloadHref } from "@/lib/download";
import { hh, load } from "@/lib/personal";
import {
  type PageProps,
  enumLabel,
  enumOptions,
  memberOptions,
  sectionMetadata,
  setup,
  todayDhaka,
} from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("income");

const PAGE_SIZE = 25;

interface Props extends PageProps {
  searchParams: Promise<{ offset?: string }>;
}

/** Income records and savings (F27): entries, recurring income, and what is left each month. */
export default async function IncomePage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/income");
  const title = t("personal.sections.income");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const offset = Math.max(0, Number((await searchParams).offset) || 0);
  const [members, summary, entries, rules] = await Promise.all([
    load(hh<Member[]>(ctx, "/members")),
    load(hh<Envelope<IncomeSummary>>(ctx, "/income/summary?months=24")),
    load(hh<Page<IncomeEntry>>(ctx, `/income?limit=${PAGE_SIZE}&offset=${offset}`)),
    load(hh<IncomeRule[]>(ctx, "/income-rules")),
  ]);

  const hid = ctx.household.id;
  const people = members.ok ? memberOptions(members.data) : [];
  const kindOptions = summary.ok ? enumOptions(t, "incomeType", summary.data.data.kinds) : [];
  const months = summary.ok ? [...summary.data.data.months].reverse() : [];
  const data = summary.ok ? summary.data.data : null;

  return (
    <PersonalShell
      ctx={ctx}
      title={title}
      description={t("personal.income.intro")}
      actions={
        <Button variant="outline" size="sm" asChild>
          <a href={downloadHref(locale, `/households/${hid}/income/export.csv`)} download>
            <Download />
            {t("personal.income.export")}
          </a>
        </Button>
      }
    >
      {data ? (
        <StatGrid>
          <Stat label={t("personal.income.income12")} value={f.compact(data.income_12m)} hint={f.bdt(data.income_12m)} />
          <Stat label={t("personal.income.costs12")} value={f.compact(data.costs_12m)} hint={f.bdt(data.costs_12m)} />
          <Stat
            label={t("personal.income.savings12")}
            value={f.compact(data.savings_12m)}
            hint={f.bdt(data.savings_12m)}
            tone={data.savings_12m.startsWith("-") ? "negative" : undefined}
          />
          <Stat
            label={t("personal.income.savingsRate")}
            value={data.savings_rate_pct === null ? "—" : f.pct(data.savings_rate_pct, 1)}
            hint={data.savings_rate_pct === null ? t("personal.income.rateEmpty") : t("personal.income.rateHint")}
          />
        </StatGrid>
      ) : (
        !summary.ok && <LoadError code={summary.code} />
      )}

      {ctx.canEdit && (
        <Panel title={t("personal.income.addTitle")}>
          <ActionForm action={addIncomeAction.bind(null, hid)} submitLabel={t("personal.income.add")} success={t("personal.income.added")}>
            <FieldGrid>
              <Field label={t("personal.date")} name="date" type="date" defaultValue={todayDhaka()} required />
              <Field label={t("personal.amount")} name="amount" type="number" inputMode="decimal" min="0.01" step="0.01" required />
              <SelectField label={t("personal.income.kind")} name="kind" options={kindOptions} required />
              <SelectField label={t("personal.member")} name="member_id" options={people} placeholder={t("personal.wholeHousehold")} />
              <Field label={t("personal.note")} name="note" maxLength={300} />
            </FieldGrid>
          </ActionForm>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel
          title={t("personal.income.byMonth")}
          description={t("personal.income.byMonthHint")}
          table
          footnote={summary.ok ? { asOf: summary.data.as_of, sources: summary.data.sources } : undefined}
        >
          {months.length === 0 ? (
            <div className="p-5"><Empty>{t("personal.income.empty")}</Empty></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.month")}</TableHead>
                  <TableHead className="text-end">{t("personal.income.earned")}</TableHead>
                  <TableHead className="text-end">{t("personal.income.spent")}</TableHead>
                  <TableHead className="text-end">{t("personal.income.left")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {months.slice(0, 12).map((m) => (
                  <TableRow key={m.month}>
                    <TableCell>{f.month(m.month)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(m.income)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(m.costs)}</TableCell>
                    <TableCell className={`text-end tabular-nums ${m.savings.startsWith("-") ? "text-destructive" : ""}`}>
                      {f.bdt(m.savings)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>

        <Panel title={t("personal.income.byKind")} description={t("personal.income.byKindHint")} table>
          {!data || data.by_kind.length === 0 ? (
            <div className="p-5"><Empty>{t("personal.income.empty")}</Empty></div>
          ) : (
            <Table>
              <TableBody>
                {data.by_kind.map((k) => (
                  <TableRow key={k.kind}>
                    <TableCell>{enumLabel(t, "incomeType", k.kind)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(k.total)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>
      </div>

      <Panel title={t("personal.income.entries")} table>
        {!entries.ok ? (
          <div className="p-5"><LoadError code={entries.code} /></div>
        ) : entries.data.items.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.income.empty")}</Empty></div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.date")}</TableHead>
                  <TableHead>{t("personal.income.kind")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("personal.note")}</TableHead>
                  <TableHead className="text-end">{t("personal.amount")}</TableHead>
                  {ctx.canEdit && <TableHead className="w-12"><span className="sr-only">{t("personal.delete")}</span></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.data.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="whitespace-nowrap">{f.date(e.date)}</TableCell>
                    <TableCell>
                      {enumLabel(t, "incomeType", e.kind)}
                      {e.recurring_id && <span className="ms-1 text-xs text-muted-foreground">({t("personal.costs.recurringShort")})</span>}
                    </TableCell>
                    <TableCell className="hidden text-secondary-foreground md:table-cell">{e.note}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(e.amount)}</TableCell>
                    {ctx.canEdit && (
                      <TableCell>
                        <DeleteButton
                          action={deleteIncomeAction.bind(null, hid, e.id)}
                          label={t("personal.income.deleteEntry")}
                          title={t("personal.income.deleteEntry")}
                        />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3 text-sm">
              <span className="text-muted-foreground">
                {t("personal.pageRange", {
                  from: f.num(offset + 1, 0),
                  to: f.num(Math.min(offset + PAGE_SIZE, entries.data.total), 0),
                  total: f.num(entries.data.total, 0),
                })}
              </span>
              <div className="flex gap-2">
                {offset > 0 && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={{ pathname: "/personal/income", query: { offset: Math.max(0, offset - PAGE_SIZE) } }}>{t("common.previous")}</Link>
                  </Button>
                )}
                {offset + PAGE_SIZE < entries.data.total && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={{ pathname: "/personal/income", query: { offset: offset + PAGE_SIZE } }}>{t("common.next")}</Link>
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </Panel>

      <Panel title={t("personal.income.recurringTitle")} description={t("personal.income.recurringIntro")}>
        <div className="flex flex-col gap-5">
          {!rules.ok ? (
            <LoadError code={rules.code} />
          ) : rules.data.length === 0 ? (
            <Empty>{t("personal.income.recurringEmpty")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {rules.data.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                  <div className="text-sm">
                    <p className="text-mono">
                      {enumLabel(t, "incomeType", r.kind)} · {f.bdt(r.amount)} · {enumLabel(t, "frequency", r.frequency)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {r.note ? `${r.note} · ` : ""}
                      {t("personal.costs.since", { date: f.date(r.start_date) })}
                    </p>
                  </div>
                  {ctx.canEdit && (
                    <div className="flex items-center gap-2">
                      <ToggleSwitch action={setIncomeRuleActiveAction.bind(null, hid, r.id)} checked={r.is_active} label={t("personal.costs.recurringActive")} />
                      <DeleteButton action={deleteIncomeRuleAction.bind(null, hid, r.id)} label={t("personal.income.deleteRecurring")} title={t("personal.income.deleteRecurring")} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {ctx.canEdit && kindOptions.length > 0 && (
            <ActionForm action={addIncomeRuleAction.bind(null, hid)} submitLabel={t("personal.income.addRecurring")} success={t("common.saved")}>
              <FieldGrid>
                <SelectField label={t("personal.income.kind")} name="kind" options={kindOptions} required />
                <Field label={t("personal.amount")} name="amount" type="number" inputMode="decimal" min="0.01" step="0.01" required />
                <SelectField label={t("personal.frequency")} name="frequency" options={enumOptions(t, "frequency", RECURRING_FREQUENCIES)} defaultValue="MONTHLY" />
                <Field label={t("personal.startDate")} name="start_date" type="date" defaultValue={todayDhaka()} required />
                <Field label={t("personal.endDate")} name="end_date" type="date" />
                <SelectField label={t("personal.member")} name="member_id" options={people} placeholder={t("personal.wholeHousehold")} />
                <Field label={t("personal.note")} name="note" maxLength={300} />
              </FieldGrid>
            </ActionForm>
          )}
        </div>
      </Panel>
      {ctx.canEdit && (
        <Panel title={t("personal.income.importTitle")} description={t("personal.income.importIntro")}>
          <ActionForm action={importIncomeAction.bind(null, hid)} submitLabel={t("personal.import.submit")}>
            <FileField label={t("personal.import.file")} name="file" accept=".csv,text/csv" />
            <TextareaField label={t("personal.import.paste")} name="csv" rows={4} placeholder={"date,amount,kind,note,member\n2026-11-01,85000,SALARY,November salary,"} />
          </ActionForm>
        </Panel>
      )}
    </PersonalShell>
  );
}
