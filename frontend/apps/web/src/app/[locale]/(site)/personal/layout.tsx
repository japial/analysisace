import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { PersonalNav } from "@/components/personal/personal-nav";
import { request } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

interface Props {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "personal" });
  // Personal pages are private: never indexed.
  return { title: { template: `%s · ${t("metaTitle")}`, default: t("metaTitle") }, robots: { index: false } };
}

/** "My money": the personal finance area (F12 to F26). Every page needs a signed-in user. */
export default async function PersonalLayout({ children, params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  // The unread count beside Alerts. Pages redirect visitors to sign-in themselves.
  const token = await getSessionToken();
  const unread = token
    ? await request<{ unread: number }>("/notifications?unread_only=true&limit=1", { token })
        .then((r) => r.unread)
        .catch(() => 0)
    : 0;
  return (
    <>
      <PersonalNav unread={unread} />
      {children}
    </>
  );
}
