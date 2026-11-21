import type { MacroNote } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { editNoteAction, generateNoteAction, publishNoteAction } from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Field } from "@/components/form/form-parts";
import { NoteFigures } from "@/components/market/note";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionButton, ActionForm, CheckField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { adminSetup } from "@/lib/market";
import { todayDhaka } from "@/lib/personal-page";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.notes" });
  return { title: t("metaTitle"), robots: { index: false } };
}

/** FR4.1 and FR4.2: drafts written from stored data, edited and published per language. */
export default async function AdminNotesPage({ params }: Props) {
  const { locale } = await params;
  const { t, f, admin } = await adminSetup(locale, "/admin/notes", "CONTENT_PUBLISH");
  const notes = await admin<MacroNote[]>("/admin/notes");

  return (
    <AdminShell title={t("adminMarket.notes.title")} description={t("adminMarket.notes.intro")}>
      <Panel title={t("adminMarket.notes.generate")}>
        <ActionForm action={generateNoteAction} submitLabel={t("adminMarket.notes.generate")} success={t("common.saved")} className="max-w-md">
          <Field label={t("adminMarket.notes.weekStart")} name="week_start" type="date" required defaultValue={todayDhaka()} />
          <CheckField label={t("adminMarket.notes.replace")} name="replace_draft" />
        </ActionForm>
      </Panel>

      {!notes.ok ? (
        <LoadError code={notes.code} />
      ) : notes.data.length === 0 ? (
        <Empty>{t("adminMarket.notes.none")}</Empty>
      ) : (
        notes.data.map((note) => (
          <Panel
            key={note.id}
            title={note.title}
            description={`${t(`adminMarket.notes.locale.${note.locale}`)} · ${t("market.macro.week", { date: f.date(note.week_start) })} · ${t("adminMarket.notes.figures", { n: note.figures.length })}`}
            actions={
              <>
                <Badge variant={note.status === "PUBLISHED" ? "success" : "secondary"} appearance="light" size="sm">
                  {t(`adminMarket.notes.status.${note.status}`)}
                </Badge>
                <ActionButton action={publishNoteAction.bind(null, note.id, note.status !== "PUBLISHED")}>
                  {note.status === "PUBLISHED" ? t("adminMarket.notes.unpublish") : t("adminMarket.notes.publish")}
                </ActionButton>
              </>
            }
          >
            <details>
              <summary className="cursor-pointer text-sm text-secondary-foreground hover:text-mono">{t("personal.edit")}</summary>
              <div className="mt-4 flex flex-col gap-5">
                <ActionForm
                  action={editNoteAction.bind(null, note.id)}
                  submitLabel={t("adminMarket.notes.save")}
                  success={t("common.saved")}
                  reset={false}
                >
                  <Field label={t("adminMarket.notes.titleField")} name="title" required maxLength={200} defaultValue={note.title} lang={note.locale} />
                  <TextareaField
                    label={t("adminMarket.notes.body")}
                    name="body"
                    required
                    maxLength={20000}
                    rows={12}
                    defaultValue={note.body}
                    hint={t("adminMarket.notes.bodyHint")}
                    lang={note.locale}
                  />
                </ActionForm>
                <NoteFigures note={note} />
              </div>
            </details>
          </Panel>
        ))
      )}
    </AdminShell>
  );
}
