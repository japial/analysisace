import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { UnsubscribeForm } from "@/components/auth/auth-forms";
import { FormMessage } from "@/components/form/form-parts";
import { ApiError, checkUnsubscribe, type UnsubscribeScope } from "@/lib/api";
import { enumLabel } from "@/lib/personal-page";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ t?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "auth" });
  return { title: t("unsubscribeTitle"), robots: { index: false } };
}

/** D34: stop one kind of alert email from the link inside it, without signing in. */
export default async function Page({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const query = await searchParams;
  const token = (Array.isArray(query.t) ? query.t[0] : query.t) ?? "";
  const t = await getTranslations("auth");
  const root = await getTranslations();

  let found: UnsubscribeScope | null = null;
  let failure: "UNSUBSCRIBE_LINK_INVALID" | "UNAVAILABLE" = "UNSUBSCRIBE_LINK_INVALID";
  if (token) {
    try {
      found = await checkUnsubscribe(token);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 400)) failure = "UNAVAILABLE";
    }
  }
  if (!found) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-center text-lg font-semibold text-mono">{t("unsubscribeTitle")}</h1>
        <FormMessage state={{ error: failure }} />
      </div>
    );
  }
  const question =
    found.scope === "DIGEST"
      ? t("unsubscribeDigest")
      : t("unsubscribeAlert", { alert: enumLabel(root, "alertType", found.scope) });
  return <UnsubscribeForm token={token} question={question} emailing={found.emailing} />;
}
