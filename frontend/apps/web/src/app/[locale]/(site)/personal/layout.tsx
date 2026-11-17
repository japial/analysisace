import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { PersonalNav } from "@/components/personal/personal-nav";

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
  return (
    <>
      <PersonalNav />
      {children}
    </>
  );
}
