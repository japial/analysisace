import { EVENT_TYPES, type ShockEvent } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import {
  createEventAction,
  deleteEventAction,
  publishEventAction,
  updateEventAction,
} from "@/app/actions/market";
import { AdminShell } from "@/components/admin/shell";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionButton, ActionForm, DeleteButton, FieldGrid, SelectField, TextareaField } from "@/components/personal/forms";
import { Badge } from "@/components/ui/badge";
import { adminSetup } from "@/lib/market";
import { eventTypeLabel } from "@/lib/market-labels";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.events" });
  return { title: t("metaTitle"), robots: { index: false } };
}

async function EventFields({ event }: { event?: ShockEvent }) {
  const t = await getTranslations();
  return (
    <>
      <FieldGrid>
        <SelectField
          label={t("adminMarket.events.type")}
          name="type"
          defaultValue={event?.type}
          options={EVENT_TYPES.map((x) => ({ value: x, label: eventTypeLabel(t, x) }))}
        />
        <Field label={t("adminMarket.events.t0")} name="t0" type="date" required defaultValue={event?.t0} />
        <Field label={t("adminMarket.events.titleEn")} name="title_en" maxLength={200} required defaultValue={event?.title_en} lang="en" />
        <Field label={t("adminMarket.events.titleBn")} name="title_bn" maxLength={200} required defaultValue={event?.title_bn} lang="bn" />
      </FieldGrid>
      <TextareaField label={t("adminMarket.events.descriptionEn")} name="description_en" required maxLength={5000} rows={3} defaultValue={event?.description_en} lang="en" />
      <TextareaField label={t("adminMarket.events.descriptionBn")} name="description_bn" required maxLength={5000} rows={3} defaultValue={event?.description_bn} lang="bn" />
      <TextareaField
        label={t("adminMarket.events.links")}
        name="source_links"
        hint={t("adminMarket.events.linksHint")}
        rows={2}
        defaultValue={event?.source_links.map((l) => `${l.label} | ${l.url}`).join("\n")}
      />
    </>
  );
}

/** FR5.1: curate the event library. Publishing computes metrics and sends FR7.2 alerts. */
export default async function AdminEventsPage({ params }: Props) {
  const { locale } = await params;
  const { t, f, admin } = await adminSetup(locale, "/admin/events", "CONTENT_PUBLISH");
  const events = await admin<ShockEvent[]>("/admin/events");

  return (
    <AdminShell title={t("adminMarket.events.title")} description={t("adminMarket.events.intro")}>
      <Panel title={t("adminMarket.events.create")}>
        <ActionForm action={createEventAction} submitLabel={t("adminMarket.events.create")} success={t("common.saved")}>
          <Field
            label={t("adminMarket.events.slug")}
            name="slug"
            required
            minLength={3}
            maxLength={80}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            hint={t("adminMarket.events.slugHint")}
            lang="en"
          />
          <EventFields />
        </ActionForm>
      </Panel>

      {!events.ok ? (
        <LoadError code={events.code} />
      ) : events.data.length === 0 ? (
        <Empty>{t("adminMarket.events.none")}</Empty>
      ) : (
        events.data.map((event) => (
          <Panel
            key={event.id}
            title={locale === "bn" ? event.title_bn : event.title_en}
            description={`${eventTypeLabel(t, event.type)} · ${f.date(event.t0)} · ${event.slug}`}
            actions={
              <>
                <Badge variant={event.published ? "success" : "secondary"} appearance="light" size="sm">
                  {event.published ? t("adminMarket.events.published") : t("adminMarket.events.draft")}
                </Badge>
                <ActionButton action={publishEventAction.bind(null, event.id, !event.published)}>
                  {event.published ? t("adminMarket.events.unpublish") : t("adminMarket.events.publish")}
                </ActionButton>
                <DeleteButton
                  action={deleteEventAction.bind(null, event.id)}
                  label={t("personal.delete")}
                  title={t("personal.delete")}
                  body={t("personal.deleteBody")}
                />
              </>
            }
          >
            <details>
              <summary className="cursor-pointer text-sm text-secondary-foreground hover:text-mono">{t("personal.edit")}</summary>
              <div className="mt-4">
                <ActionForm
                  action={updateEventAction.bind(null, event.id)}
                  submitLabel={t("adminMarket.events.save")}
                  success={t("common.saved")}
                  reset={false}
                >
                  <EventFields event={event} />
                </ActionForm>
              </div>
            </details>
          </Panel>
        ))
      )}
    </AdminShell>
  );
}
