import { formatDate } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { Download } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import {
  ConsentsForm,
  DeleteAccount,
  PasswordForm,
  ProfileForm,
} from "@/components/account/account-forms";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { digitsFor } from "@/lib/locale";
import { requireUser } from "@/lib/session";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "account" });
  return { title: t("metaTitle"), robots: { index: false } };
}

function Section({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {intro && <p className="max-w-2xl text-sm text-muted-foreground">{intro}</p>}
        {children}
      </CardContent>
    </Card>
  );
}

export default async function AccountPage({ params }: Props) {
  const { locale: rawLocale } = await params;
  const locale = rawLocale as Locale;
  setRequestLocale(locale);
  const user = await requireUser(locale, "/account");
  const t = await getTranslations();
  const dates = { language: locale, digits: digitsFor(locale) };

  return (
    <>
      <Toolbar
        title={t("account.title")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("account.title") }]}
      />
      <div className="container flex flex-col gap-5 lg:gap-7.5">
        <Section title={t("account.profileTitle")}>
          <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <div className="flex items-center gap-2">
              <dt className="text-muted-foreground">{t("account.role")}</dt>
              <dd>
                <Badge variant="primary" appearance="light">
                  {t(`roles.${user.role}.name`)}
                </Badge>
              </dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="text-muted-foreground">{t("account.memberSince")}</dt>
              <dd>{formatDate(user.created_at, dates)}</dd>
            </div>
            {user.last_login_at && (
              <div className="flex items-center gap-2">
                <dt className="text-muted-foreground">{t("account.lastSignIn")}</dt>
                <dd>{formatDate(user.last_login_at, { ...dates, withTime: true })}</dd>
              </div>
            )}
          </dl>
          <ProfileForm user={user} />
        </Section>

        <Section title={t("account.passwordTitle")} intro={t("account.passwordIntro")}>
          <PasswordForm />
        </Section>

        <Section title={t("account.consentsTitle")} intro={t("account.consentsIntro")}>
          <ConsentsForm user={user} />
        </Section>

        <Section title={t("account.dataTitle")} intro={t("account.dataIntro")}>
          <Button variant="outline" asChild className="self-start">
            {/* A plain link: the route answers with a file download. */}
            <a href={`/${locale}/account/export`} download>
              <Download />
              {t("account.export")}
            </a>
          </Button>
        </Section>

        <Section title={t("account.deleteTitle")} intro={t("account.deleteIntro")}>
          <div>
            <DeleteAccount />
          </div>
        </Section>
      </div>
    </>
  );
}
