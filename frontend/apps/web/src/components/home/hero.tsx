/**
 * Landing page hero: the FIRE promise, the two calls to action and an illustration of a
 * FIRE plan. The illustration uses a fictional household and says so; it is not data.
 *
 * Its figures agree with each other: costs of 85,000 a month are 10,20,000 a year, and at a
 * 4% withdrawal rate the FIRE number is 25 times that, 2,55,00,000. Investable capital of
 * 96,90,000 is 38% of it. Income of 1,28,800 less costs leaves 43,800, a 34% savings rate.
 */
import { ArrowRight, Check, Flame, HandHeart, PiggyBank, Scale, TrendingUp, type LucideIcon } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";

const PREVIEW = {
  fireNumber: "25500000",
  invested: "9690000",
  progressPct: "38",
  fireAge: "51",
  age: "38",
  savingsRate: "34",
  zakat: "99264.75",
};

/** The three levers under the progress bar, each with its sample figure. */
const LEVERS: { key: "assets" | "capital" | "earnings"; icon: LucideIcon; value: string }[] = [
  { key: "assets", icon: Scale, value: "14850000" },
  { key: "capital", icon: TrendingUp, value: "9690000" },
  { key: "earnings", icon: PiggyBank, value: "43800" },
];

export async function Hero({ signedIn }: { signedIn: boolean }) {
  const t = await getTranslations("home");
  const f = formatterFor(await getLocale());

  return (
    <section className="relative isolate overflow-hidden bg-brand-navy text-white">
      {/* Background: a faint grid and two soft brand-teal glows. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 opacity-[0.07] [background-image:linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_75%)]"
      />
      <div aria-hidden="true" className="absolute -top-32 -end-24 -z-10 size-[28rem] rounded-full bg-brand-teal/25 blur-3xl" />
      <div aria-hidden="true" className="absolute -bottom-40 -start-24 -z-10 size-[24rem] rounded-full bg-brand-teal-deep/40 blur-3xl" />

      <div className="container grid items-center gap-12 py-16 lg:grid-cols-[1.1fr_1fr] lg:gap-16 lg:py-24">
        <div className="flex flex-col items-start gap-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-white/80">
            <Flame className="size-3.5 text-brand-teal" aria-hidden="true" />
            {t("hero.eyebrow")}
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            {t("hero.title")}
          </h1>
          <p className="max-w-xl text-lg text-pretty text-white/75">{t("hero.lead")}</p>
          <div className="flex flex-wrap gap-3">
            <Button size="lg" asChild className="bg-brand-teal text-brand-navy hover:bg-brand-teal/90">
              <Link href={signedIn ? "/personal/fire" : "/signup"}>
                {signedIn ? t("hero.ctaPlan") : t("hero.ctaSignUp")}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white">
              <Link href="/#fire">{t("hero.ctaExplore")}</Link>
            </Button>
          </div>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-white/70">
            {(["sources", "bilingual", "noTips"] as const).map((key) => (
              <li key={key} className="flex items-center gap-1.5">
                <Check className="size-4 text-brand-teal" aria-hidden="true" />
                {t(`hero.trust.${key}`)}
              </li>
            ))}
          </ul>
        </div>

        {/* Product illustration: a FIRE plan with the three ACE levers. */}
        <figure className="relative mx-auto w-full max-w-md lg:max-w-none">
          <div className="relative rounded-2xl border border-white/10 bg-card p-5 text-card-foreground shadow-2xl shadow-black/40 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-mono">{t("preview.title")}</p>
                <p className="text-xs text-muted-foreground">{t("preview.subtitle")}</p>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                <Flame className="size-3.5" aria-hidden="true" />
                {t("preview.fireAge", { age: f.num(PREVIEW.fireAge, 0) })}
              </span>
            </div>

            <div className="mt-5 flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3 text-xs">
                <span className="text-secondary-foreground">{t("preview.progress")}</span>
                <span className="text-lg font-semibold tabular-nums text-mono">{f.pct(PREVIEW.progressPct, 0)}</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-gradient-to-r from-brand-teal-deep to-brand-teal" style={{ width: `${PREVIEW.progressPct}%` }} />
              </div>
              <div className="flex justify-between gap-3 text-[11px] text-muted-foreground tabular-nums">
                <span>{t("preview.invested", { amount: f.compact(PREVIEW.invested) })}</span>
                <span>{t("preview.fireNumber", { amount: f.compact(PREVIEW.fireNumber) })}</span>
              </div>
            </div>

            <ul className="mt-5 grid grid-cols-3 gap-2 border-t border-border pt-4">
              {LEVERS.map(({ key, icon: Icon, value }) => (
                <li key={key} className="flex flex-col gap-0.5">
                  <span className="flex items-center gap-1 text-[11px] font-medium text-primary">
                    <Icon className="size-3.5" aria-hidden="true" />
                    {t(`preview.${key}`)}
                  </span>
                  <span className="text-sm font-semibold tabular-nums text-mono">{f.compact(value)}</span>
                  <span className="text-[11px] leading-tight text-muted-foreground">{t(`preview.${key}Note`)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-border pt-3 text-end text-[11px] text-muted-foreground">{t("preview.source")}</p>
          </div>

          {/* Two floating notes: the biggest lever, and Zakat kept in the plan. */}
          <div className="absolute -top-16 end-4 hidden max-w-[16rem] rounded-xl border border-border bg-card px-3.5 py-2.5 text-card-foreground shadow-xl sm:block">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <PiggyBank className="size-3.5 text-primary" aria-hidden="true" />
              {t("preview.savingsRate")}
            </p>
            <p className="mt-0.5 text-sm font-semibold text-mono">{f.pct(PREVIEW.savingsRate, 0)}</p>
          </div>
          <div className="absolute bottom-6 -start-3 hidden rounded-xl border border-border bg-card px-3.5 py-2.5 text-card-foreground shadow-xl sm:block lg:-start-8">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <HandHeart className="size-3.5 text-primary" aria-hidden="true" />
              {t("preview.zakat")}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums text-mono">{f.bdt(PREVIEW.zakat)}</p>
          </div>
          <figcaption className="mt-10 text-center text-xs text-white/50">{t("preview.label")}</figcaption>
        </figure>
      </div>
    </section>
  );
}
