import type { Category, SetupStatus } from "@analysisace/core";

import { quickStartAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, FieldGrid } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import { type PageProps, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("setup");

/**
 * Quick start (D22): the basics in one form. Income and fixed costs become monthly rules,
 * day-to-day costs this month's estimate, and savings one holding per kind. Everything it
 * makes can be changed afterwards on the usual pages.
 */
export default async function SetupPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t } = await setup(locale, "/personal/setup");
  const title = t("personal.sections.setup");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [status, categories] = await Promise.all([
    load(hh<SetupStatus>(ctx, "/setup/status")),
    load(hh<Category[]>(ctx, "/categories")),
  ]);
  if (!status.ok) {
    return (
      <PersonalShell ctx={ctx} title={title}>
        <LoadError code={status.code} />
      </PersonalShell>
    );
  }
  const s = status.data;
  const done = Object.fromEntries(s.steps.map((step) => [step.key, step.done]));
  const name = (key: string) => {
    const c = categories.ok ? categories.data.find((x) => x.key === key) : undefined;
    return c ? (locale === "bn" ? c.name_bn : c.name_en) : key;
  };
  // Kinds come from the API's configuration; a kind added there without a label shows its key.
  const savingLabel = (key: string) => {
    const k = `personal.setup.savings.${key}`;
    return t.has(k as never) ? t(k as never) : key;
  };
  const money = { type: "number", inputMode: "decimal", min: "0", step: "0.01", placeholder: "0" } as const;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.setup.intro")}>
      {!ctx.canEdit ? (
        <Empty>{t("personal.setup.viewerOnly")}</Empty>
      ) : (
        <ActionForm action={quickStartAction.bind(null, ctx.household.id, locale)} submitLabel={t("personal.setup.submit")}>
          <div className="flex flex-col gap-5">
            <Panel title={t("personal.setup.youTitle")} description={t("personal.setup.youIntro")}>
              <FieldGrid>
                <Field label={t("personal.setup.birthYear")} name="birth_year" type="number" min="1926" max="2011" step="1" placeholder="1990" hint={done.you ? t("personal.setup.alreadyDone") : undefined} />
              </FieldGrid>
            </Panel>

            <Panel title={t("personal.setup.incomeTitle")} description={t("personal.setup.incomeIntro")}>
              <FieldGrid>
                <Field label={t("personal.setup.monthlyIncome")} name="monthly_income" {...money} hint={done.income ? t("personal.setup.alreadyIncome") : t("personal.setup.monthlyIncomeHint")} />
              </FieldGrid>
            </Panel>

            <Panel title={t("personal.setup.costsTitle")} description={t("personal.setup.costsIntro")}>
              <div className="flex flex-col gap-4">
                {done.costs && <p className="text-sm text-muted-foreground">{t("personal.setup.alreadyCosts")}</p>}
                <h3 className="text-sm font-semibold text-mono">{t("personal.setup.fixed")}</h3>
                <FieldGrid>
                  {s.fixed_categories.map((key) => (
                    <Field key={key} label={t("personal.setup.perMonth", { name: name(key) })} name={`cost_${key}`} {...money} />
                  ))}
                </FieldGrid>
                <h3 className="text-sm font-semibold text-mono">{t("personal.setup.variable")}</h3>
                <FieldGrid>
                  {s.variable_categories.map((key) => (
                    <Field key={key} label={t("personal.setup.perMonth", { name: name(key) })} name={`cost_${key}`} {...money} />
                  ))}
                </FieldGrid>
              </div>
            </Panel>

            <Panel title={t("personal.setup.savingsTitle")} description={t("personal.setup.savingsIntro")}>
              <div className="flex flex-col gap-4">
                {done.savings && <p className="text-sm text-muted-foreground">{t("personal.setup.alreadySavings")}</p>}
                <FieldGrid>
                  {s.savings_kinds.map((key) => (
                    <Field key={key} label={savingLabel(key)} name={`saving_${key}`} {...money} />
                  ))}
                </FieldGrid>
                <p className="text-xs text-muted-foreground">{t("personal.setup.savingsLater")}</p>
              </div>
            </Panel>
          </div>
        </ActionForm>
      )}
      {/* D38: everything here can also be added one page at a time. */}
      <Link href="/personal" className="self-start text-sm font-medium text-primary hover:underline">
        {t("personal.setup.skip")}
      </Link>
    </PersonalShell>
  );
}
