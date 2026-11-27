import type { Locale } from "@analysisace/i18n";
import {
  ArrowRight,
  BadgeCheck,
  CalendarClock,
  ChartColumn,
  Check,
  ChevronDown,
  Compass,
  Eye,
  Fingerprint,
  Flame,
  HandHeart,
  House,
  Landmark,
  type LucideIcon,
  MapPin,
  MessageCircleQuestion,
  Newspaper,
  Percent,
  PiggyBank,
  Receipt,
  Scale,
  ScrollText,
  ShieldCheck,
  Target,
  TrendingUp,
  UsersRound,
  Zap,
} from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { Hero } from "@/components/home/hero";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { getCurrentUser } from "@/lib/session";
import { cn } from "@/lib/utils";

/** The three FIRE ideas, in the order a person works through them. */
const FIRE_STEPS = [
  { key: "number", icon: Target },
  { key: "rate", icon: PiggyBank },
  { key: "date", icon: CalendarClock },
] as const;

/**
 * Illustration for "savings rate decides more than returns": years from zero savings to a
 * FIRE number of 25 times yearly costs, at a 5% return after inflation and a 4% withdrawal
 * rate. n = ln(1 + 25 x (1 - s) x 0.05 / s) / ln(1.05). Fixed text, not data; bar widths are
 * the years as a share of 52.
 */
const RATE_ROWS = [
  { rate: "10", years: "51", width: "98%" },
  { rate: "20", years: "37", width: "71%" },
  { rate: "30", years: "28", width: "54%" },
  { rate: "40", years: "22", width: "42%" },
  { rate: "50", years: "17", width: "32%" },
  { rate: "60", years: "12", width: "24%" },
  { rate: "70", years: "9", width: "17%" },
] as const;

/** The ACE levers: each links to the first page of its area under My money. */
const LEVERS = [
  { key: "earnings", icon: PiggyBank, href: "/personal/income" },
  { key: "capital", icon: TrendingUp, href: "/personal/portfolio" },
  { key: "assets", icon: Scale, href: "/personal/assets" },
] as const;

const LEVER_ITEMS = ["a", "b", "c"] as const;

/** What a FIRE plan has to deal with in Bangladesh, each backed by a feature. */
const LOCAL = [
  { key: "inflation", icon: Percent },
  { key: "halal", icon: BadgeCheck },
  { key: "family", icon: UsersRound },
  { key: "home", icon: House },
  { key: "zakat", icon: HandHeart },
  { key: "stress", icon: Zap },
] as const;

const QUESTIONS = [
  { key: "when", icon: CalendarClock, href: "/personal/fire" },
  { key: "enough", icon: Target, href: "/personal/fire" },
  { key: "crash", icon: Zap, href: "/personal/fire" },
  { key: "savings", icon: Receipt, href: "/personal/income" },
  { key: "zakat", icon: HandHeart, href: "/personal/zakat" },
  { key: "halal", icon: ShieldCheck, href: "/personal/market-check" },
] as const;

/** Stock tools, one kind of capital among many. `wide` tiles span two columns on large screens. */
const STOCK_TOOLS = [
  { key: "shariah", icon: BadgeCheck, href: "/shariah", wide: true },
  { key: "basket", icon: ChartColumn, href: "/shariah", wide: false },
  { key: "rates", icon: Percent, href: "/rates", wide: false },
  { key: "shocks", icon: Zap, href: "/events", wide: false },
  { key: "macro", icon: Newspaper, href: "/macro", wide: false },
  { key: "regime", icon: Compass, href: "/regime", wide: true },
] as const;

const TRUST = [
  { key: "traceable", icon: Eye },
  { key: "rules", icon: ScrollText },
  { key: "advice", icon: MessageCircleQuestion },
  { key: "privacy", icon: Fingerprint },
  { key: "local", icon: MapPin },
  { key: "own", icon: Landmark },
] as const;

const FAQ = ["fire", "retire", "promise", "what", "shares", "advice", "data", "privacy", "language"] as const;

function SectionHeading({ eyebrow, title, lead, id }: { eyebrow?: string; title: string; lead?: string; id: string }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
      {eyebrow && (
        <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold tracking-wide text-primary uppercase">
          {eyebrow}
        </span>
      )}
      <h2 id={id} className="font-display text-3xl font-bold tracking-tight text-balance text-mono sm:text-4xl">
        {title}
      </h2>
      {lead && <p className="text-lg text-pretty text-secondary-foreground">{lead}</p>}
    </div>
  );
}

function IconBadge({ icon: Icon, className }: { icon: LucideIcon; className?: string }) {
  return (
    <span className={cn("flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary", className)}>
      <Icon className="size-5" aria-hidden="true" />
    </span>
  );
}

function Tile({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "group relative flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-6 transition-all motion-safe:hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * The landing page, built around FIRE (financial independence): what FIRE means, why the
 * savings rate matters most, the three ACE levers that move a FIRE date, what a plan must
 * handle in Bangladesh, the questions it answers, the stock tools as one kind of capital,
 * how to start, principles, common questions and a call to action. Projections are
 * described as projections; the copy never tells anyone what to buy or sell (PRD section 0).
 */
export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const t = await getTranslations();
  const f = formatterFor(locale);
  const user = await getCurrentUser();
  const signedIn = user !== null;
  const start = signedIn ? "/personal/fire" : "/signup";

  return (
    <div className="flex flex-col">
      <Hero signedIn={signedIn} />

      {/* What FIRE means: three ideas and the one formula behind them. */}
      <section id="fire" aria-labelledby="fire-title" className="container scroll-mt-20 py-16 lg:py-24">
        <SectionHeading id="fire-title" eyebrow={t("home.fire.eyebrow")} title={t("home.fire.title")} lead={t("home.fire.lead")} />
        <ol className="mt-12 grid gap-4 md:grid-cols-3 lg:gap-5">
          {FIRE_STEPS.map(({ key, icon }, index) => (
            <li key={key}>
              <Tile>
                <div className="flex items-center justify-between">
                  <IconBadge icon={icon} />
                  <span className="font-display text-3xl font-bold text-primary/25 tabular-nums" aria-hidden="true">
                    {f.num(String(index + 1), 0)}
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-mono">{t(`home.fire.steps.${key}.title`)}</h3>
                <p className="grow text-sm text-secondary-foreground">{t(`home.fire.steps.${key}.body`)}</p>
              </Tile>
            </li>
          ))}
        </ol>
        <div className="mx-auto mt-8 flex max-w-3xl flex-col items-center gap-2 rounded-2xl border border-dashed border-primary/40 bg-primary/5 px-6 py-5 text-center">
          <p className="font-display text-lg font-semibold text-balance text-mono sm:text-xl">{t("home.fire.formula")}</p>
          <p className="text-sm text-pretty text-secondary-foreground">{t("home.fire.formulaNote")}</p>
        </div>
      </section>

      {/* Savings rate: a fixed illustration of years to FIRE by savings rate. */}
      <section aria-labelledby="rate-title" className="border-y border-border bg-muted/40 py-16 lg:py-24">
        <div className="container grid items-center gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <div className="flex flex-col gap-4">
            <span className="self-start rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold tracking-wide text-primary uppercase">
              {t("home.rate.eyebrow")}
            </span>
            <h2 id="rate-title" className="font-display text-3xl font-bold tracking-tight text-balance text-mono sm:text-4xl">
              {t("home.rate.title")}
            </h2>
            <p className="text-lg text-pretty text-secondary-foreground">{t("home.rate.lead")}</p>
            <p className="text-sm text-secondary-foreground">{t("home.rate.body")}</p>
            <Button asChild className="self-start">
              <Link href={signedIn ? "/personal/income" : "/signup"}>
                {t("home.rate.cta")}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
          </div>
          <figure className="rounded-2xl border border-border bg-card p-5 sm:p-6">
            <figcaption className="text-sm font-semibold text-mono">{t("home.rate.chartTitle")}</figcaption>
            <table className="mt-4 w-full text-sm">
              <thead className="sr-only">
                <tr>
                  <th scope="col">{t("home.rate.colRate")}</th>
                  <th scope="col">{t("home.rate.colYears")}</th>
                </tr>
              </thead>
              <tbody>
                {RATE_ROWS.map((row) => (
                  <tr key={row.rate}>
                    <th scope="row" className="w-24 py-1.5 pe-3 text-start font-medium text-secondary-foreground tabular-nums">
                      {t("home.rate.saving", { rate: f.pct(row.rate, 0) })}
                    </th>
                    <td className="py-1.5">
                      <div className="flex items-center gap-3">
                        <div className="h-3 grow overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-gradient-to-r from-brand-teal-deep to-brand-teal" style={{ width: row.width }} />
                        </div>
                        <span className="w-20 shrink-0 text-end font-semibold text-mono tabular-nums">
                          {t("home.rate.years", { years: f.num(row.years, 0) })}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">{t("home.rate.assumptions")}</p>
          </figure>
        </div>
      </section>

      {/* The ACE levers that move a FIRE date. */}
      <section id="ace" aria-labelledby="ace-title" className="container scroll-mt-20 py-16 lg:py-24">
        <SectionHeading id="ace-title" eyebrow={t("home.ace.eyebrow")} title={t("home.ace.title")} lead={t("home.ace.lead")} />
        <ul className="mt-12 grid gap-4 lg:grid-cols-3 lg:gap-5">
          {LEVERS.map(({ key, icon, href }) => (
            <li key={key}>
              <Tile className="gap-4 bg-gradient-to-br from-primary/10 via-card to-card">
                <IconBadge icon={icon} />
                <div>
                  <h3 className="font-display text-2xl font-semibold text-mono">{t(`home.ace.pillars.${key}.title`)}</h3>
                  <p className="mt-1 text-sm font-medium text-primary">{t(`home.ace.pillars.${key}.tagline`)}</p>
                </div>
                <p className="flex gap-2 rounded-lg bg-primary/5 px-3 py-2 text-sm text-mono">
                  <Flame className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                  {t(`home.ace.pillars.${key}.lever`)}
                </p>
                <ul className="flex grow flex-col gap-2.5">
                  {LEVER_ITEMS.map((item) => (
                    <li key={item} className="flex gap-2 text-sm text-secondary-foreground">
                      <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                      {t(`home.ace.pillars.${key}.items.${item}`)}
                    </li>
                  ))}
                </ul>
                <Link
                  href={signedIn ? href : "/signup"}
                  className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-primary after:absolute after:inset-0 after:rounded-2xl hover:underline"
                >
                  {t(`home.ace.pillars.${key}.cta`)}
                  <ArrowRight className="size-4 rtl:rotate-180" aria-hidden="true" />
                </Link>
              </Tile>
            </li>
          ))}
        </ul>
      </section>

      {/* FIRE in Bangladesh: what a plan has to handle here. */}
      <section aria-labelledby="local-title" className="relative isolate overflow-hidden bg-brand-navy py-16 text-white lg:py-24">
        <div aria-hidden="true" className="absolute -top-24 end-0 -z-10 size-96 rounded-full bg-brand-teal/20 blur-3xl" />
        <div className="container">
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold tracking-wide text-brand-teal uppercase">
              {t("home.local.eyebrow")}
            </span>
            <h2 id="local-title" className="font-display text-3xl font-bold tracking-tight text-balance sm:text-4xl">
              {t("home.local.title")}
            </h2>
            <p className="text-lg text-pretty text-white/75">{t("home.local.lead")}</p>
          </div>
          <ul className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {LOCAL.map(({ key, icon }) => (
              <li key={key} className="flex gap-4">
                <IconBadge icon={icon} className="bg-white/10 text-brand-teal" />
                <div className="flex flex-col gap-1">
                  <h3 className="font-semibold">{t(`home.local.items.${key}.title`)}</h3>
                  <p className="text-sm text-white/70">{t(`home.local.items.${key}.body`)}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Questions people ask about reaching independence. */}
      <section aria-labelledby="questions-title" className="container py-16 lg:py-24">
        <SectionHeading id="questions-title" title={t("home.questions.title")} lead={t("home.questions.lead")} />
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5">
          {QUESTIONS.map(({ key, icon, href }) => (
            <li key={key}>
              <Link
                href={signedIn ? href : "/signup"}
                className="block h-full rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <Tile>
                  <IconBadge icon={icon} />
                  <p className="font-display text-lg font-semibold text-balance text-mono">“{t(`home.questions.items.${key}.q`)}”</p>
                  <p className="grow text-sm text-secondary-foreground">{t(`home.questions.items.${key}.a`)}</p>
                  <ArrowRight
                    className="size-4 text-primary transition-transform motion-safe:group-hover:translate-x-1 rtl:rotate-180"
                    aria-hidden="true"
                  />
                </Tile>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {/* Stock tools: one kind of capital, so a quieter section. The Shariah screen gets the most room. */}
      <section aria-labelledby="tools-title" className="border-y border-border bg-muted/40 py-16 lg:py-24">
        <div className="container">
          <SectionHeading id="tools-title" eyebrow={t("home.tools.eyebrow")} title={t("home.tools.title")} lead={t("home.tools.lead")} />
          <ul className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3 lg:gap-5">
            {STOCK_TOOLS.map(({ key, icon, href, wide }) => (
              <li key={key} className={cn(wide && "lg:col-span-2")}>
                <Tile className={cn(wide && "bg-gradient-to-br from-primary/10 via-card to-card")}>
                  <IconBadge icon={icon} />
                  <h3 className="text-lg font-semibold text-mono">{t(`home.tools.features.${key}.title`)}</h3>
                  <p className="grow text-sm text-secondary-foreground">{t(`home.tools.features.${key}.body`)}</p>
                  <Link
                    href={href}
                    className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-primary after:absolute after:inset-0 after:rounded-2xl hover:underline"
                  >
                    {t(`home.tools.features.${key}.cta`)}
                    <ArrowRight className="size-4 rtl:rotate-180" aria-hidden="true" />
                  </Link>
                </Tile>
              </li>
            ))}
            <li>
              <Tile className="justify-center border-dashed bg-transparent">
                <IconBadge icon={Eye} />
                <p className="text-sm font-medium text-mono">{t("home.tools.watch")}</p>
              </Tile>
            </li>
          </ul>
        </div>
      </section>

      {/* Three steps, joined by a line on wide screens. */}
      <section aria-labelledby="steps-title" className="container py-16 lg:py-24">
        <SectionHeading id="steps-title" title={t("home.steps.title")} />
        <ol className="relative mt-12 grid gap-8 md:grid-cols-3">
          <span aria-hidden="true" className="absolute start-[16%] end-[16%] top-6 hidden h-px bg-border md:block" />
          {(["one", "two", "three"] as const).map((key, index) => (
            <li key={key} className="relative flex flex-col items-center gap-3 text-center">
              <span className="flex size-12 items-center justify-center rounded-full bg-primary font-display text-lg font-bold text-primary-foreground ring-8 ring-background">
                {f.num(String(index + 1), 0)}
              </span>
              <h3 className="text-lg font-semibold text-mono">{t(`home.steps.items.${key}.title`)}</h3>
              <p className="max-w-xs text-sm text-secondary-foreground">{t(`home.steps.items.${key}.body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Principles. */}
      <section aria-labelledby="trust-title" className="border-y border-border bg-muted/40 py-16 lg:py-24">
        <div className="container">
          <SectionHeading id="trust-title" title={t("home.trust.title")} lead={t("home.trust.lead")} />
          <ul className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {TRUST.map(({ key, icon }) => (
              <li key={key} className="flex gap-4">
                <IconBadge icon={icon} />
                <div className="flex flex-col gap-1">
                  <h3 className="font-semibold text-mono">{t(`home.trust.items.${key}.title`)}</h3>
                  <p className="text-sm text-secondary-foreground">{t(`home.trust.items.${key}.body`)}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Questions and answers, readable without scripts. */}
      <section aria-labelledby="faq-title" className="container max-w-3xl py-16 lg:py-24">
        <SectionHeading id="faq-title" title={t("home.faq.title")} />
        <div className="mt-10 flex flex-col gap-3">
          {FAQ.map((key) => (
            <details key={key} className="group rounded-xl border border-border bg-card open:shadow-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 font-medium text-mono [&::-webkit-details-marker]:hidden">
                {t(`home.faq.items.${key}.q`)}
                <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="px-5 pb-5 text-sm text-secondary-foreground">{t(`home.faq.items.${key}.a`)}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Closing call to action. */}
      <section aria-labelledby="final-title" className="container pb-16 lg:pb-24">
        <div className="relative isolate overflow-hidden rounded-3xl bg-brand-navy px-6 py-14 text-center text-white sm:px-12">
          <div aria-hidden="true" className="absolute -top-24 start-1/2 -z-10 size-96 -translate-x-1/2 rounded-full bg-brand-teal/25 blur-3xl" />
          <Flame className="mx-auto size-8 text-brand-teal" aria-hidden="true" />
          <h2 id="final-title" className="mt-4 font-display text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            {t("home.final.title")}
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-white/75">{t("home.final.lead")}</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild className="bg-brand-teal text-brand-navy hover:bg-brand-teal/90">
              <Link href={start}>
                {signedIn ? t("home.hero.ctaPlan") : t("home.hero.ctaSignUp")}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white">
              <Link href="/#fire">{t("home.hero.ctaExplore")}</Link>
            </Button>
          </div>
        </div>
        <div className="mt-8">
          <Disclaimer />
        </div>
      </section>
    </div>
  );
}
