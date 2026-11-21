import type { Permission } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Toolbar } from "@/components/layout/toolbar";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { requireUser } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
}

const SCREENS = [
  { key: "users", href: "/admin/users", permission: "USERS_MANAGE" },
  { key: "roles", href: "/admin/roles", permission: "USERS_MANAGE" },
  { key: "data", href: "/admin/data", permission: "DATA_REVIEW" },
  { key: "shariah", href: "/admin/shariah", permission: "SHARIAH_OVERRIDE" },
  { key: "events", href: "/admin/events", permission: "CONTENT_PUBLISH" },
  { key: "notes", href: "/admin/notes", permission: "CONTENT_PUBLISH" },
  { key: "bankFlags", href: "/admin/bank-flags", permission: "CONFIG_MANAGE" },
  { key: "audit", href: "/admin/audit", permission: "AUDIT_VIEW" },
] as const satisfies readonly { key: string; href: string; permission: Permission }[];

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "adminMarket.hub" });
  return { title: t("metaTitle"), robots: { index: false } };
}

/** The admin screens this person may open. The API checks each permission again. */
export default async function AdminHubPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const user = await requireUser(locale as Locale, "/admin");
  // Reviewers check financial figures on the Shariah screen too.
  const screens = SCREENS.filter(
    (s) =>
      user.permissions.includes(s.permission) ||
      (s.key === "shariah" && user.permissions.includes("DATA_REVIEW")),
  );
  if (screens.length === 0) notFound();
  const t = await getTranslations();

  return (
    <>
      <Toolbar
        title={t("adminMarket.hub.title")}
        description={t("adminMarket.hub.intro")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("adminMarket.hub.title") }]}
      />
      <div className="container pb-10">
        <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {screens.map((s) => (
            <li key={s.key}>
              <Card className="relative h-full transition-colors hover:border-primary">
                <CardContent className="flex flex-col gap-1.5">
                  <Link href={s.href} className="font-semibold text-mono after:absolute after:inset-0 hover:underline">
                    {t(`adminMarket.hub.${s.key}.title`)}
                  </Link>
                  <p className="text-sm text-secondary-foreground">{t(`adminMarket.hub.${s.key}.description`)}</p>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
