import { BANK_STATUSES, type BankFlag } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { deleteBankFlagAction, setBankFlagAction } from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, DeleteButton, FieldGrid, SelectField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { adminSetup } from "@/lib/market";
import { enumLabel } from "@/lib/personal-page";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.bankFlags" });
  return { title: t("metaTitle"), robots: { index: false } };
}

const STATUS_VARIANT = { NORMAL: "secondary", RESTRUCTURING: "warning", RESTRICTED: "destructive" } as const;

async function FlagFields({ flag }: { flag?: BankFlag }) {
  const t = await getTranslations();
  return (
    <>
      <FieldGrid>
        <Field
          label={t("adminMarket.bankFlags.bank")}
          name="bank"
          required
          maxLength={200}
          defaultValue={flag?.bank}
          readOnly={flag !== undefined}
          hint={flag ? undefined : t("adminMarket.bankFlags.bankHint")}
          lang="en"
        />
        <SelectField
          label={t("adminMarket.bankFlags.status")}
          name="status"
          defaultValue={flag?.status ?? "RESTRUCTURING"}
          options={BANK_STATUSES.map((s) => ({ value: s, label: enumLabel(t, "bankStatus", s) }))}
        />
      </FieldGrid>
      <TextareaField label={t("adminMarket.bankFlags.noteEn")} name="note_en" required maxLength={2000} rows={3} defaultValue={flag?.note_en} lang="en" />
      <TextareaField label={t("adminMarket.bankFlags.noteBn")} name="note_bn" required maxLength={2000} rows={3} defaultValue={flag?.note_bn} lang="bn" />
      <TextareaField
        label={t("adminMarket.bankFlags.links")}
        name="source_links"
        hint={t("adminMarket.bankFlags.linksHint")}
        rows={2}
        defaultValue={flag?.source_links.map((l) => `${l.title} | ${l.url}`).join("\n")}
      />
    </>
  );
}

/** FR26.5: neutral, sourced notices about banks (permission CONFIG_MANAGE). */
export default async function AdminBankFlagsPage({ params }: Props) {
  const { locale } = await params;
  const { t, f, admin } = await adminSetup(locale, "/admin/bank-flags", "CONFIG_MANAGE");
  const flags = await admin<BankFlag[]>("/admin/bank-flags");

  return (
    <AdminShell title={t("adminMarket.bankFlags.title")} description={t("adminMarket.bankFlags.intro")}>
      <Panel title={t("adminMarket.bankFlags.add")}>
        <ActionForm action={setBankFlagAction} submitLabel={t("adminMarket.bankFlags.save")} success={t("common.saved")}>
          <FlagFields />
        </ActionForm>
      </Panel>

      {!flags.ok ? (
        <LoadError code={flags.code} />
      ) : flags.data.length === 0 ? (
        <Empty>{t("adminMarket.bankFlags.none")}</Empty>
      ) : (
        flags.data.map((flag) => (
          <Panel
            key={flag.id}
            title={flag.bank}
            description={t("adminMarket.bankFlags.updated", { date: f.date(flag.updated_at) })}
            actions={
              <>
                <Badge variant={STATUS_VARIANT[flag.status]} appearance="light" size="sm">
                  {enumLabel(t, "bankStatus", flag.status)}
                </Badge>
                <DeleteButton
                  action={deleteBankFlagAction.bind(null, flag.id)}
                  label={t("adminMarket.bankFlags.delete")}
                  title={t("adminMarket.bankFlags.delete")}
                  body={t("adminMarket.bankFlags.deleteBody")}
                />
              </>
            }
          >
            <div className="flex flex-col gap-3 text-sm">
              <p className="text-secondary-foreground">{locale === "bn" ? flag.note_bn : flag.note_en}</p>
              {flag.source_links.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {flag.source_links.map((link) => (
                    <li key={link.url}>
                      <a href={link.url} rel="noopener" className="text-primary underline">
                        {link.title}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              <details>
                <summary className="cursor-pointer text-secondary-foreground hover:text-mono">{t("adminMarket.bankFlags.edit")}</summary>
                <div className="mt-4">
                  <ActionForm action={setBankFlagAction} submitLabel={t("adminMarket.bankFlags.save")} success={t("common.saved")} reset={false}>
                    <FlagFields flag={flag} />
                  </ActionForm>
                </div>
              </details>
            </div>
          </Panel>
        ))
      )}
    </AdminShell>
  );
}
