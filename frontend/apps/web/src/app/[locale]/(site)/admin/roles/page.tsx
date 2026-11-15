import type { Locale } from "@analysisace/i18n";
import { Check, Minus } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Toolbar } from "@/components/layout/toolbar";
import { Card, CardTable } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listRoles } from "@/lib/api";
import { requirePermission, requireToken } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "admin" });
  return { title: t("rolesMetaTitle"), robots: { index: false } };
}

export default async function AdminRolesPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = rawLocale as Locale;
  setRequestLocale(locale);
  await requirePermission(locale, "/admin/roles", "USERS_MANAGE");

  const t = await getTranslations();
  const { roles, permissions } = await listRoles(await requireToken());

  return (
    <>
      <Toolbar
        title={t("admin.rolesTitle")}
        description={t("admin.rolesIntro")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("admin.rolesTitle") }]}
      />
      <div className="container">
        <Card>
          <CardTable>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-72">{t("admin.permission")}</TableHead>
                    {roles.map(({ role }) => (
                      <TableHead key={role} className="min-w-40 align-top">
                        <span className="block text-mono">{t(`roles.${role}.name`)}</span>
                        <span className="block text-xs font-normal normal-case text-muted-foreground">
                          {t(`roles.${role}.description`)}
                        </span>
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {permissions.map((permission) => (
                    <TableRow key={permission}>
                      <TableHead scope="row" className="h-auto py-3 text-start font-normal">
                        <span className="block font-medium text-mono">
                          {t(`permissions.${permission}.name`)}
                        </span>
                        <span className="block text-sm text-muted-foreground">
                          {t(`permissions.${permission}.description`)}
                        </span>
                      </TableHead>
                      {roles.map((definition) => {
                        const allowed = definition.permissions.includes(permission);
                        return (
                          <TableCell key={definition.role}>
                            {allowed ? (
                              <Check className="size-5 text-green-600" aria-hidden />
                            ) : (
                              <Minus className="size-5 text-muted-foreground" aria-hidden />
                            )}
                            <span className="sr-only">
                              {allowed ? t("common.yes") : t("common.no")}
                            </span>
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardTable>
        </Card>
      </div>
    </>
  );
}
