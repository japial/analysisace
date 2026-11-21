import type { Member, ZakatSnapshot } from "@analysisace/core";

import { createZakatAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, FieldGrid, SelectField } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, memberOptions, sectionMetadata, setup, todayDhaka } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("zakat");

/** Zakat snapshots (FR13.1 to FR13.4). The rules are provisional until an advisor approves them. */
export default async function ZakatPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/zakat");
  const title = t("personal.sections.zakat");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const [snapshots, members] = await Promise.all([
    load(hh<ZakatSnapshot[]>(ctx, "/zakat/snapshots")),
    load(hh<Member[]>(ctx, "/members")),
  ]);
  const consented = ctx.user.consents.RELIGIOUS_PREFERENCES?.granted ?? false;
  const memberName = (id: string) =>
    (members.ok && members.data.find((m) => m.id === id)?.display_name) || "—";
  const you = members.ok ? members.data.find((m) => m.is_you) : undefined;

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.zakat.intro")}>
      <Alert variant="info" appearance="light" role="note">
        <AlertDescription>{t("personal.zakat.provisional")}</AlertDescription>
      </Alert>

      {!consented ? (
        <Panel title={t("personal.zakat.consentTitle")}>
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-secondary-foreground">{t("personal.zakat.consentBody")}</p>
            <Button variant="primary" size="sm" asChild>
              <Link href="/account">{t("personal.zakat.consentLink")}</Link>
            </Button>
          </div>
        </Panel>
      ) : (
        ctx.canEdit &&
        members.ok && (
          <Panel title={t("personal.zakat.newTitle")} description={t("personal.zakat.newIntro")}>
            <ActionForm action={createZakatAction.bind(null, ctx.household.id)} submitLabel={t("personal.zakat.calculate")}>
              <FieldGrid>
                <SelectField label={t("personal.member")} name="member_id" options={memberOptions(members.data)} defaultValue={you?.id} />
                <Field label={t("personal.date")} name="date" type="date" defaultValue={todayDhaka()} />
                <SelectField
                  label={t("personal.zakat.nisabBasis")}
                  name="nisab_basis"
                  options={[
                    { value: "GOLD", label: enumLabel(t, "nisab", "GOLD") },
                    { value: "SILVER", label: enumLabel(t, "nisab", "SILVER") },
                  ]}
                  placeholder={t("personal.zakat.memberDefault")}
                  hint={t("personal.zakat.nisabHint")}
                />
                <Field label={t("personal.zakat.pricePerGram")} name="price_per_gram" type="number" inputMode="decimal" min="0.01" step="0.01" hint={t("personal.zakat.pricePerGramHint")} />
                <SelectField
                  label={t("personal.zakat.sharesMethod")}
                  name="shares_method"
                  options={[
                    { value: "MARKET_VALUE", label: enumLabel(t, "sharesMethod", "MARKET_VALUE") },
                    { value: "ZAKATABLE_ASSETS", label: enumLabel(t, "sharesMethod", "ZAKATABLE_ASSETS") },
                  ]}
                  placeholder={t("personal.zakat.configDefault")}
                />
              </FieldGrid>
            </ActionForm>
          </Panel>
        )
      )}

      <Panel title={t("personal.zakat.history")} table>
        {!snapshots.ok ? (
          <div className="p-5"><LoadError code={snapshots.code} /></div>
        ) : snapshots.data.length === 0 ? (
          <div className="p-5"><Empty>{t("personal.zakat.empty")}</Empty></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("personal.date")}</TableHead>
                <TableHead>{t("personal.member")}</TableHead>
                <TableHead className="hidden text-end sm:table-cell">{t("personal.zakat.netZakatable")}</TableHead>
                <TableHead className="text-end">{t("personal.zakat.due")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {snapshots.data.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link href={`/personal/zakat/${s.id}`} className="text-primary hover:underline">{f.date(s.date)}</Link>
                  </TableCell>
                  <TableCell>{memberName(s.member_id)}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.bdt(s.net_zakatable)}</TableCell>
                  <TableCell className="text-end font-medium tabular-nums text-mono">{f.bdt(s.zakat_due)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </PersonalShell>
  );
}
