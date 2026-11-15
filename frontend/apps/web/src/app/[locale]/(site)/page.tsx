import type { Locale } from "@analysisace/i18n";
import { ArrowRight, ChartLine, ScrollText, Wallet } from "lucide-react";
import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";

const FEATURES = [
  { key: "shariah", icon: ScrollText },
  { key: "macro", icon: ChartLine },
  { key: "household", icon: Wallet },
] as const;

export default function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = use(params);
  setRequestLocale(locale as Locale);
  const t = useTranslations();

  return (
    <div className="container flex flex-col gap-10 py-10 lg:gap-14 lg:py-16">
      <section className="max-w-3xl">
        <h1 className="font-display text-3xl font-bold tracking-tight text-balance text-mono sm:text-5xl">
          {t("home.title")}
        </h1>
        <p className="mt-4 text-lg text-secondary-foreground">{t("home.subtitle")}</p>
        <Button size="lg" asChild className="mt-6">
          <Link href="/companies">
            {t("home.browseCompanies")}
            <ArrowRight />
          </Link>
        </Button>
      </section>

      <section aria-labelledby="features-title">
        <h2 id="features-title" className="text-xl font-semibold text-mono">
          {t("home.featuresTitle")}
        </h2>
        <ul className="mt-5 grid gap-5 md:grid-cols-3 lg:gap-7.5">
          {FEATURES.map(({ key, icon: Icon }) => (
            <li key={key}>
              <Card className="h-full">
                <CardContent className="flex flex-col gap-3">
                  <span className="flex size-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <h3 className="font-semibold text-mono">{t(`home.features.${key}.title`)}</h3>
                  <p className="grow text-sm text-secondary-foreground">
                    {t(`home.features.${key}.body`)}
                  </p>
                  <Badge variant="secondary" appearance="light" className="self-start">
                    {t("common.inDevelopment")}
                  </Badge>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
