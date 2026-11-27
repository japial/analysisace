import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ConfirmEmailChangeForm } from "@/components/auth/auth-forms";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ token?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "auth" });
  return { title: t("changeTitle"), robots: { index: false } };
}

/** D39: confirm a new sign-in email from the link sent to it. Works without signing in. */
export default async function Page({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const query = await searchParams;
  const token = (Array.isArray(query.token) ? query.token[0] : query.token) ?? "";
  return <ConfirmEmailChangeForm token={token} />;
}
