import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ResetPasswordForm } from "@/components/auth/auth-forms";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string | string[]; token?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "auth" });
  return { title: t("resetTitle"), robots: { index: false } };
}

export default async function Page({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const query = await searchParams;
  const token = (Array.isArray(query.token) ? query.token[0] : query.token) ?? "";
  return <ResetPasswordForm token={token} />;
}
