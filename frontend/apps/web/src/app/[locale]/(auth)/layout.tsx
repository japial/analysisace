import type { Locale } from "@analysisace/i18n";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { LocaleSwitcher } from "@/components/layout/locale-switcher";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";

interface Props {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

/** Metronic "classic" auth layout: logo above a centred card. */
export default async function AuthLayout({ children, params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const t = await getTranslations("common");

  return (
    <div className="flex grow flex-col bg-muted/60">
      <div className="flex justify-end gap-1 p-3">
        <LocaleSwitcher />
        <ThemeToggle />
      </div>
      <main className="flex grow flex-col items-center justify-center px-4 pb-10">
        <Link href="/" className="mb-5">
          <Logo markClassName="size-10" wordmarkClassName="text-2xl" />
        </Link>
        <Card className="w-full max-w-[400px]">
          <CardContent className="p-6">{children}</CardContent>
        </Card>
        <p className="mt-5 max-w-[400px] text-center text-xs text-muted-foreground">
          {t("disclaimer")}
        </p>
      </main>
    </div>
  );
}
