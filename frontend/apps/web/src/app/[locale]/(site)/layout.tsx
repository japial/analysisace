import type { Locale } from "@analysisace/i18n";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { SiteNavbar } from "@/components/layout/site-navbar";
import { VerifyEmailBanner } from "@/components/layout/verify-email-banner";
import { navItems } from "@/lib/nav";
import { getCurrentUser } from "@/lib/session";

interface Props {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

/**
 * Metronic Layout 9: fixed header, menu bar, centred content, footer.
 * Reading the session makes these pages render per request.
 */
export default async function SiteLayout({ children, params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const t = await getTranslations("common");
  const user = await getCurrentUser();
  const items = navItems(user);

  return (
    <div className="flex grow flex-col pt-(--header-height) [--header-height:70px]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-20 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        {t("skipToContent")}
      </a>
      <SiteHeader user={user} items={items} />
      <SiteNavbar items={items} />
      <VerifyEmailBanner user={user} />
      <main id="main" className="flex grow flex-col">
        <div className="grow">{children}</div>
        <SiteFooter />
      </main>
    </div>
  );
}
