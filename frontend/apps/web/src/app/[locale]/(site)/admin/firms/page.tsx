import type { AdminFirm } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { createFirmAction, setFirmActiveAction, setFirmSeatLimitAction } from "@/app/actions/firm";
import { Field } from "@/components/form/form-parts";
import { Toolbar } from "@/components/layout/toolbar";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionForm, FieldGrid, TextareaField, ToggleSwitch } from "@/components/personal/forms";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminSetup } from "@/lib/market";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "firm.admin" });
  return { title: t("title"), robots: { index: false } };
}

/** Platform admin for firms (FR9.3, D30): create a firm with its first admin, set seat limits,
 * switch a firm off. Missing (404) while firm features are switched off. */
export default async function AdminFirmsPage({ params }: Props) {
  const { locale } = await params;
  const { t, f, admin } = await adminSetup(locale, "/admin/firms", "FIRMS_MANAGE");
  const list = await admin<AdminFirm[]>("/admin/firms");
  if (!list.ok && list.status === 404) notFound();

  return (
    <>
      <Toolbar
        title={t("firm.admin.title")}
        description={t("firm.admin.intro")}
        breadcrumbs={[
          { label: t("nav.home"), href: "/" },
          { label: t("adminMarket.hub.title"), href: "/admin" },
          { label: t("firm.admin.title") },
        ]}
      />
      <div className="container flex flex-col gap-5 pb-10 lg:gap-7.5">
        <Panel title={t("firm.admin.listTitle")} table>
          {!list.ok ? (
            <div className="p-5"><LoadError code={list.code} /></div>
          ) : list.data.length === 0 ? (
            <div className="p-5"><Empty>{t("firm.admin.none")}</Empty></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("firm.admin.name")}</TableHead>
                  <TableHead>{t("firm.admin.seats")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("firm.admin.created")}</TableHead>
                  <TableHead>{t("firm.admin.active")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.map((firm) => (
                  <TableRow key={firm.id}>
                    <TableCell className="text-mono">{firm.name}</TableCell>
                    <TableCell>
                      <ActionForm action={setFirmSeatLimitAction.bind(null, firm.id)} submitLabel={t("common.save")} reset={false} className="flex-row items-end gap-2">
                        <Field
                          label={t("firm.admin.seatLimitFor", { used: f.num(String(firm.seats_used), 0), name: firm.name })}
                          name="seat_limit"
                          type="number"
                          min="1"
                          max="500"
                          defaultValue={String(firm.seat_limit)}
                          required
                        />
                      </ActionForm>
                    </TableCell>
                    <TableCell className="hidden whitespace-nowrap md:table-cell">{f.date(firm.created_at)}</TableCell>
                    <TableCell>
                      <ToggleSwitch action={setFirmActiveAction.bind(null, firm.id)} checked={firm.is_active} label={t("firm.admin.activeFor", { name: firm.name })} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Panel>

        <Panel title={t("firm.admin.createTitle")} description={t("firm.admin.createIntro")}>
          <ActionForm action={createFirmAction} submitLabel={t("firm.admin.create")} success={t("common.saved")}>
            <FieldGrid>
              <Field label={t("firm.admin.name")} name="name" minLength={2} maxLength={200} required />
              <Field label={t("firm.admin.seatLimit")} name="seat_limit" type="number" min="1" max="500" defaultValue="5" required />
              <Field label={t("firm.admin.adminEmail")} name="admin_email" type="email" required hint={t("firm.admin.adminEmailHint")} />
            </FieldGrid>
            <TextareaField label={t("firm.disclaimer")} name="report_disclaimer" rows={3} maxLength={1000} hint={t("firm.disclaimerHint")} />
          </ActionForm>
        </Panel>
      </div>
    </>
  );
}
