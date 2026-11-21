/**
 * Landing page hero: the promise, the two calls to action and an illustration of the
 * product. The illustration uses a fictional demo company and says so; it is not data.
 */
import { ArrowRight, BadgeCheck, Check, HandHeart, Percent } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";

/** Illustration only: ratio, limit, and the bar's share of the limit. */
const PREVIEW_RULES = [
  { key: "debt", value: "13.27", limit: "30", width: "44%" },
  { key: "cash", value: "8.84", limit: "30", width: "29%" },
  { key: "income", value: "1.20", limit: "5", width: "24%" },
] as const;

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
            <span className="size-1.5 rounded-full bg-brand-teal" aria-hidden="true" />
            {t("hero.eyebrow")}
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            {t("hero.title")}
          </h1>
          <p className="max-w-xl text-lg text-pretty text-white/75">{t("hero.lead")}</p>
          <div className="flex flex-wrap gap-3">
            <Button size="lg" asChild className="bg-brand-teal text-brand-navy hover:bg-brand-teal/90">
              <Link href={signedIn ? "/personal" : "/signup"}>
                {signedIn ? t("hero.ctaMyMoney") : t("hero.ctaSignUp")}
                <ArrowRight />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white">
              <Link href="/shariah">{t("hero.ctaExplore")}</Link>
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

        {/* Product illustration. Decorative for screen readers apart from its label. */}
        <figure className="relative mx-auto w-full max-w-md lg:max-w-none">
          <div className="relative rounded-2xl border border-white/10 bg-card p-5 text-card-foreground shadow-2xl shadow-black/40 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-mono" lang="en">
                  DMPHARMA
                </p>
                <p className="text-xs text-muted-foreground" lang="en">
                  {t("preview.company")}
                </p>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                <BadgeCheck className="size-3.5" aria-hidden="true" />
                {t("preview.status")}
              </span>
            </div>
            <ul className="mt-5 flex flex-col gap-4">
              {PREVIEW_RULES.map((rule) => (
                <li key={rule.key} className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between gap-3 text-xs">
                    <span className="text-secondary-foreground">{t(`preview.${rule.key}`)}</span>
                    <span className="flex items-center gap-2 tabular-nums">
                      <span className="font-semibold text-mono">{f.pct(rule.value)}</span>
                      <span className="text-muted-foreground">{t("preview.limit", { value: f.pct(rule.limit, 0) })}</span>
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: rule.width }} />
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-5 border-t border-border pt-3 text-end text-[11px] text-muted-foreground">{t("preview.source")}</p>
          </div>

          {/* Two floating notes showing the other halves of the product. */}
          <div className="absolute -top-16 end-4 hidden max-w-[16rem] rounded-xl border border-border bg-card px-3.5 py-2.5 text-card-foreground shadow-xl sm:block">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Percent className="size-3.5 text-primary" aria-hidden="true" />
              {t("preview.rate")}
            </p>
            <p className="mt-0.5 text-sm font-semibold text-mono">{t("preview.rateValue")}</p>
          </div>
          <div className="absolute bottom-6 -start-3 hidden rounded-xl border border-border bg-card px-3.5 py-2.5 text-card-foreground shadow-xl sm:block lg:-start-8">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <HandHeart className="size-3.5 text-primary" aria-hidden="true" />
              {t("preview.zakat")}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums text-mono">{f.bdt("99264.75")}</p>
          </div>
          <figcaption className="mt-10 text-center text-xs text-white/50">{t("preview.label")}</figcaption>
        </figure>
      </div>
    </section>
  );
}
