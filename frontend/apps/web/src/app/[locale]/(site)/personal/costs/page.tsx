import {
  type Category,
  type CostSummary,
  type Envelope,
  type Expense,
  type Member,
  type Page,
  RECURRING_FREQUENCIES,
  type RecurringRule,
} from "@analysisace/core";
import { Download } from "lucide-react";

import {
  addCategoryAction,
  addExpenseAction,
  addRecurringAction,
  deleteCategoryAction,
  deleteExpenseAction,
  deleteRecurringAction,
  importExpensesAction,
  setRecurringActiveAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel, Stat, StatGrid } from "@/components/personal/display";
import {
  ActionForm,
  DeleteButton,
  FieldGrid,
  FileField,
  SelectField,
  TextareaField,
  ToggleSwitch,
} from "@/components/personal/forms";
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

export const generateMetadata = sectionMetadata("costs");

const PAGE_SIZE = 25;

interface Props extends PageProps {
  searchParams: Promise<{ offset?: string }>;
}

/** Daily cost records (F12): entry, monthly and yearly totals, recurring costs, CSV. */
export default async function CostsPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/costs");
  const title = t("personal.sections.costs");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const offset = Math.max(0, Number((await searchParams).offset) || 0);
  const [categories, members, summary, expenses, recurring] = await Promise.all([
    load(hh<Category[]>(ctx, "/categories")),
    load(hh<Member[]>(ctx, "/members")),
    load(hh<Envelope<CostSummary>>(ctx, "/costs/summary?months=24")),
    load(hh<Page<Expense>>(ctx, `/expenses?limit=${PAGE_SIZE}&offset=${offset}`)),
    load(hh<RecurringRule[]>(ctx, "/recurring")),
  ]);

  const hid = ctx.household.id;
  const cats = categories.ok ? categories.data : [];
  const catName = (id: string) => {
    const c = cats.find((x) => x.id === id);
    return c ? (locale === "bn" ? c.name_bn : c.name_en) : "—";
  };
  const categoryOptions = cats.map((c) => ({ value: c.id, label: locale === "bn" ? c.name_bn : c.name_en }));
  const people = members.ok ? memberOptions(members.data) : [];
  const months = summary.ok ? [...summary.data.data.months].reverse() : [];

  return (
    <PersonalShell
      ctx={ctx}
      title={title}
      description={t("personal.costs.intro")}
      actions={
        <Button variant="outline" size="sm" asChild>
          <a href={downloadHref(locale, `/households/${hid}/costs/export.csv`)} download>
            <Download />
            {t("personal.costs.export")}
          </a>
        </Button>
      }
    >
      {summary.ok ? (
        <StatGrid>
          <Stat label={t("personal.costs.trailing12")} value={f.compact(summary.data.data.trailing_12_months)} hint={f.bdt(summary.data.data.trailing_12_months)} />
          {months[0] && (
            <Stat label={t("personal.costs.thisMonth", { month: f.month(months[0].month) })} value={f.bdt(months[0].total)} />
          )}
          {summary.data.data.years.slice(-2).reverse().map((y) => (
            <Stat key={y.year} label={t("personal.costs.year", { year: f.num(y.year, 0).replace(/,/g, "") })} value={f.compact(y.total)} hint={f.bdt(y.total)} />
          ))}
        </StatGrid>
      ) : (
        <LoadError code={summary.code} />
      )}

      {ctx.canEdit && (
        <Panel title={t("personal.costs.addTitle")}>
          {cats.length === 0 ? (
            <Empty>{t("personal.costs.noCategories")}</Empty>
          ) : (
            <ActionForm action={addExpenseAction.bind(null, hid)} submitLabel={t("personal.costs.add")} success={t("personal.costs.added")}>
              <FieldGrid>
                <Field label={t("personal.date")} name="date" type="date" defaultValue={todayDhaka()} required />
                <Field label={t("personal.amount")} name="amount" type="number" inputMode="decimal" min="0.01" step="0.01" required />
                <SelectField label={t("personal.category")} name="category_id" options={categoryOptions} required />
                <SelectField label={t("personal.member")} name="member_id" options={people} placeholder={t("personal.wholeHousehold")} />
                <Field label={t("personal.note")} name="note" maxLength={300} />
              </FieldGrid>
            </ActionForm>
          )}
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel
          title={t("personal.costs.byMonth")}
          description={summary.ok && summary.data.data.price_base_month ? t("personal.costs.realHint", { month: f.month(summary.data.data.price_base_month) }) : undefined}
          table
          footnote={summary.ok ? { asOf: summary.data.as_of, sources: summary.data.sources } : undefined}
        >
          {months.length === 0 ? (
            <div className="p-5"><Empty>{t("personal.costs.empty")}</Empty></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.month")}</TableHead>
                  <TableHead className="text-end">{t("personal.costs.spent")}</TableHead>
                  <TableHead className="text-end">{t("personal.costs.inTodaysPrices")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {months.slice(0, 12).map((m) => (
                  <TableRow key={m.month}>
                    <TableCell>{f.month(m.month)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(m.total)}</TableCell>
                    <TableCell className="text-end text-secondary-foreground tabular-nums">{f.bdt(m.real_total)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>

        <Panel title={t("personal.costs.byCategory")} description={t("personal.costs.byCategoryHint")} table>
          {!summary.ok || summary.data.data.by_category.length === 0 ? (
            <div className="p-5"><Empty>{t("personal.costs.empty")}</Empty></div>
          ) : (
            <Table>
              <TableBody>
                {summary.data.data.by_category.map((c) => (
                  <TableRow key={c.category_id}>
                    <TableCell>{catName(c.category_id)}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(c.total)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>
      </div>

      <Panel title={t("personal.costs.entries")} table>
        {!expenses.ok ? (
          <div className="p-5"><LoadError code={expenses.code} /></div>
        ) : expenses.data.items.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.costs.empty")}</Empty></div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("personal.date")}</TableHead>
                  <TableHead>{t("personal.category")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("personal.note")}</TableHead>
                  <TableHead className="text-end">{t("personal.amount")}</TableHead>
                  {ctx.canEdit && <TableHead className="w-12"><span className="sr-only">{t("personal.delete")}</span></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {expenses.data.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="whitespace-nowrap">{f.date(e.date)}</TableCell>
                    <TableCell>
                      {catName(e.category_id)}
                      {e.recurring_id && <span className="ms-1 text-xs text-muted-foreground">({t("personal.costs.recurringShort")})</span>}
                    </TableCell>
                    <TableCell className="hidden text-secondary-foreground md:table-cell">{e.note}</TableCell>
                    <TableCell className="text-end tabular-nums">{f.bdt(e.amount)}</TableCell>
                    {ctx.canEdit && (
                      <TableCell>
                        <DeleteButton
                          action={deleteExpenseAction.bind(null, hid, e.id)}
                          label={t("personal.costs.deleteEntry")}
                          title={t("personal.costs.deleteEntry")}
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
                  to: f.num(Math.min(offset + PAGE_SIZE, expenses.data.total), 0),
                  total: f.num(expenses.data.total, 0),
                })}
              </span>
              <div className="flex gap-2">
                {offset > 0 && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={{ pathname: "/personal/costs", query: { offset: Math.max(0, offset - PAGE_SIZE) } }}>{t("common.previous")}</Link>
                  </Button>
                )}
                {offset + PAGE_SIZE < expenses.data.total && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={{ pathname: "/personal/costs", query: { offset: offset + PAGE_SIZE } }}>{t("common.next")}</Link>
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </Panel>

      <Panel title={t("personal.costs.recurringTitle")} description={t("personal.costs.recurringIntro")}>
        <div className="flex flex-col gap-5">
          {!recurring.ok ? (
            <LoadError code={recurring.code} />
          ) : recurring.data.length === 0 ? (
            <Empty>{t("personal.costs.recurringEmpty")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {recurring.data.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                  <div className="text-sm">
                    <p className="text-mono">
                      {catName(r.category_id)} · {f.bdt(r.amount)} · {enumLabel(t, "frequency", r.frequency)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {r.note ? `${r.note} · ` : ""}
                      {t("personal.costs.since", { date: f.date(r.start_date) })}
                    </p>
                  </div>
                  {ctx.canEdit && (
                    <div className="flex items-center gap-2">
                      <ToggleSwitch action={setRecurringActiveAction.bind(null, hid, r.id)} checked={r.is_active} label={t("personal.costs.recurringActive")} />
                      <DeleteButton action={deleteRecurringAction.bind(null, hid, r.id)} label={t("personal.costs.deleteRecurring")} title={t("personal.costs.deleteRecurring")} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {ctx.canEdit && cats.length > 0 && (
            <ActionForm action={addRecurringAction.bind(null, hid)} submitLabel={t("personal.costs.addRecurring")} success={t("common.saved")}>
              <FieldGrid>
                <SelectField label={t("personal.category")} name="category_id" options={categoryOptions} required />
                <Field label={t("personal.amount")} name="amount" type="number" inputMode="decimal" min="0.01" step="0.01" required />
                <SelectField label={t("personal.frequency")} name="frequency" options={enumOptions(t, "frequency", RECURRING_FREQUENCIES)} defaultValue="MONTHLY" />
                <Field label={t("personal.startDate")} name="start_date" type="date" defaultValue={todayDhaka()} required />
                <Field label={t("personal.endDate")} name="end_date" type="date" />
                <Field label={t("personal.note")} name="note" maxLength={300} />
              </FieldGrid>
            </ActionForm>
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-7.5">
        <Panel title={t("personal.costs.categoriesTitle")} description={t("personal.costs.categoriesIntro")}>
          <div className="flex flex-col gap-4">
            <ul className="flex flex-wrap gap-2">
              {cats.map((c) => (
                <li key={c.id} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm">
                  {locale === "bn" ? c.name_bn : c.name_en}
                  {ctx.canEdit && !c.is_default && (
                    <DeleteButton action={deleteCategoryAction.bind(null, hid, c.id)} label={t("personal.costs.deleteCategory")} title={t("personal.costs.deleteCategory")} />
                  )}
                </li>
              ))}
            </ul>
            {ctx.canEdit && (
              <ActionForm action={addCategoryAction.bind(null, hid)} submitLabel={t("personal.costs.addCategory")} className="max-w-sm">
                <Field label={t("personal.costs.categoryName")} name="name" maxLength={80} required />
              </ActionForm>
            )}
          </div>
        </Panel>

        {ctx.canEdit && (
          <Panel title={t("personal.costs.importTitle")} description={t("personal.costs.importIntro")}>
            <ActionForm action={importExpensesAction.bind(null, hid)} submitLabel={t("personal.import.submit")}>
              <FileField label={t("personal.import.file")} name="file" accept=".csv,text/csv" />
              <TextareaField label={t("personal.import.paste")} name="csv" rows={4} placeholder={"date,amount,category,note\n2026-11-01,1200,food_bazar,Weekly bazar"} />
            </ActionForm>
          </Panel>
        )}
      </div>
    </PersonalShell>
  );
}
