import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { SignInForm } from "@/components/auth/auth-forms";
import { redirect } from "@/i18n/navigation";
import { getCurrentUser, safeReturnPath } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string | string[]; token?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "auth" });
  return { title: t("signInTitle"), robots: { index: false } };
}

export default async function Page({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const query = await searchParams;
  const next = safeReturnPath(Array.isArray(query.next) ? query.next[0] : query.next);
  // Someone already signed in has no use for this page.
  if (await getCurrentUser()) redirect({ href: next, locale: locale as Locale });
  return <SignInForm next={next} />;
}
