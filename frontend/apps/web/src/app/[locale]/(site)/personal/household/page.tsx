import type { Member } from "@analysisace/core";

import {
  addMemberAction,
  createHouseholdAction,
  removeMemberAction,
  renameHouseholdAction,
  updateMemberAction,
} from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { LoadError, Panel } from "@/components/personal/display";
import { ActionForm, DeleteButton, FieldGrid, SelectField } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Badge } from "@/components/ui/badge";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, enumOptions, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("household");

const ROLES = ["OWNER", "EDITOR", "VIEWER"] as const;

/** Household, its members and their roles (F24, FR24.1 and FR24.2). */
export default async function HouseholdPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/household");
  const title = t("personal.sections.household");
  if (!ctx.household) return <PersonalShell ctx={ctx} title={title}>{null}</PersonalShell>;

  const members = await load(hh<Member[]>(ctx, "/members"));
  const hid = ctx.household.id;
  const nisab = [
    { value: "GOLD", label: enumLabel(t, "nisab", "GOLD") },
    { value: "SILVER", label: enumLabel(t, "nisab", "SILVER") },
  ];

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.household.intro")}>
      {ctx.isOwner && (
        <Panel title={t("personal.household.renameTitle")}>
          <ActionForm action={renameHouseholdAction.bind(null, hid)} submitLabel={t("common.save")} success={t("common.saved")} reset={false} className="max-w-md">
            <Field label={t("personal.household.name")} name="name" defaultValue={ctx.household.name} maxLength={120} required />
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.household.members")} description={t("personal.household.membersIntro")}>
        {!members.ok ? (
          <LoadError code={members.code} />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {members.data.map((m) => {
              // A person may edit their own Zakat details; an owner may edit anyone's.
              const editable = ctx.isOwner || m.is_you;
              return (
                <li key={m.id} className="flex flex-col gap-3 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-2 font-medium text-mono">
                        {m.display_name}
                        {m.is_you && <Badge variant="primary" appearance="light" size="sm">{t("personal.household.you")}</Badge>}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {enumLabel(t, "householdRole", m.role)}
                        {m.birth_year ? ` · ${t("personal.household.born", { year: String(m.birth_year) })}` : ""}
                        {` · ${m.has_login ? t("personal.household.hasLogin") : t("personal.household.noLogin")}`}
                        {m.hawl_date ? ` · ${t("personal.household.hawl", { date: f.date(m.hawl_date) })}` : ""}
                      </p>
                    </div>
                    {(ctx.isOwner || m.is_you) && !(m.is_you && m.role === "OWNER") && (
                      <DeleteButton
                        action={removeMemberAction.bind(null, hid, m.id)}
                        label={m.is_you ? t("personal.household.leave") : t("personal.household.remove")}
                        title={m.is_you ? t("personal.household.leave") : t("personal.household.remove")}
                      />
                    )}
                  </div>
                  {editable && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-secondary-foreground hover:text-mono">{t("personal.edit")}</summary>
                      <ActionForm action={updateMemberAction.bind(null, hid, m.id)} submitLabel={t("common.save")} success={t("common.saved")} reset={false} className="mt-3">
                        <FieldGrid>
                          <Field label={t("personal.household.displayName")} name="display_name" id={`name-${m.id}`} defaultValue={m.display_name} maxLength={120} required />
                          <Field label={t("personal.household.birthYear")} name="birth_year" id={`by-${m.id}`} type="number" min="1900" max="2100" defaultValue={m.birth_year ?? ""} />
                          {ctx.isOwner && (
                            <SelectField label={t("personal.household.role")} name="role" options={enumOptions(t, "householdRole", ROLES)} defaultValue={m.role} />
                          )}
                          <Field label={t("personal.household.hawlDate")} name="hawl_date" id={`hawl-${m.id}`} type="date" defaultValue={m.hawl_date ?? ""} hint={t("personal.household.hawlHint")} />
                          <SelectField label={t("personal.zakat.nisabBasis")} name="nisab_basis" options={nisab} defaultValue={m.nisab_basis ?? undefined} placeholder={t("personal.notSet")} />
                        </FieldGrid>
                      </ActionForm>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      {ctx.isOwner && (
        <Panel title={t("personal.household.addTitle")} description={t("personal.household.addIntro")}>
          <ActionForm action={addMemberAction.bind(null, hid)} submitLabel={t("personal.household.add")} success={t("common.saved")}>
            <FieldGrid>
              <Field label={t("personal.household.displayName")} name="display_name" maxLength={120} required />
              <SelectField label={t("personal.household.role")} name="role" options={enumOptions(t, "householdRole", ROLES)} defaultValue="VIEWER" />
              <Field label={t("personal.household.birthYear")} name="birth_year" type="number" min="1900" max="2100" />
              <Field label={t("auth.email")} name="email" type="email" lang="en" hint={t("personal.household.emailHint")} />
            </FieldGrid>
          </ActionForm>
        </Panel>
      )}

      <Panel title={t("personal.household.anotherTitle")} description={t("personal.household.anotherIntro")}>
        <ActionForm action={createHouseholdAction} submitLabel={t("personal.household.create")} className="max-w-md">
          <Field label={t("personal.household.name")} name="name" id="new-household" maxLength={120} required />
        </ActionForm>
      </Panel>
    </PersonalShell>
  );
}
