import type { Locale } from "@analysisace/i18n";
import {
  ArrowRight,
  BadgeCheck,
  Bell,
  ChartColumn,
  Check,
  ChevronDown,
  Compass,
  Eye,
  FileText,
  Fingerprint,
  Flame,
  HandHeart,
  Languages,
  Landmark,
  type LucideIcon,
  MapPin,
  MessageCircleQuestion,
  Newspaper,
  Percent,
  Receipt,
  ScrollText,
  ShieldCheck,
  UsersRound,
  Wallet,
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

const QUESTIONS = [
  { key: "halal", icon: BadgeCheck, href: "/shariah" },
  { key: "rates", icon: Percent, href: "/rates" },
  { key: "shock", icon: Zap, href: "/events" },
  { key: "zakat", icon: HandHeart, href: "/personal/zakat" },
  { key: "tax", icon: FileText, href: "/personal/tax" },
  { key: "fire", icon: Flame, href: "/personal/fire" },
] as const;

/** Market features. `wide` tiles span two columns on large screens. */
const MARKET_FEATURES = [
  { key: "shariah", icon: BadgeCheck, href: "/shariah", wide: true },
  { key: "basket", icon: ChartColumn, href: "/shariah", wide: false },
  { key: "rates", icon: Percent, href: "/rates", wide: false },
  { key: "shocks", icon: Zap, href: "/events", wide: false },
  { key: "macro", icon: Newspaper, href: "/macro", wide: false },
  { key: "regime", icon: Compass, href: "/regime", wide: true },
] as const;

const MONEY_FEATURES = [
  { key: "wealth", icon: Wallet },
  { key: "check", icon: ShieldCheck },
  { key: "tax", icon: FileText },
  { key: "plans", icon: Flame },
  { key: "costs", icon: Receipt },
  { key: "family", icon: UsersRound },
  { key: "alerts", icon: Bell },
] as const;

/** What the Zakat tile lists as counted; labels reuse the asset type names. */
const ZAKAT_COUNTED = ["CASH", "GOLD", "EQUITY", "ISLAMIC_FIXED_INCOME", "BUSINESS"] as const;

const TRUST = [
  { key: "traceable", icon: Eye },
  { key: "rules", icon: ScrollText },
  { key: "advice", icon: MessageCircleQuestion },
  { key: "privacy", icon: Fingerprint },
  { key: "local", icon: MapPin },
  { key: "own", icon: Landmark },
] as const;

const FAQ = ["advice", "method", "data", "privacy", "language"] as const;

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
 * The landing page: what analysisACE answers, the market features, My money, how to start,
 * the principles it is built on, common questions and a call to action. Copy describes past
 * behaviour and features; it never tells anyone what to buy or sell (PRD section 0).
 */
export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale as Locale);
  const t = await getTranslations();
  const f = formatterFor(locale);
  const user = await getCurrentUser();
  const signedIn = user !== null;

  return (
    <div className="flex flex-col">
      <Hero signedIn={signedIn} />

      {/* Questions people ask: the product framed by the reader's own decisions. */}
      <section aria-labelledby="questions-title" className="container py-16 lg:py-24">
        <SectionHeading id="questions-title" title={t("home.questions.title")} lead={t("home.questions.lead")} />
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5">
          {QUESTIONS.map(({ key, icon, href }) => (
            <li key={key}>
              <Link href={href} className="block h-full rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
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

      {/* Markets: a bento grid, the Shariah screen given the most room. */}
      <section aria-labelledby="markets-title" className="border-y border-border bg-muted/40 py-16 lg:py-24">
        <div className="container">
          <SectionHeading
            id="markets-title"
            eyebrow={t("home.markets.eyebrow")}
            title={t("home.markets.title")}
            lead={t("home.markets.lead")}
          />
          <ul className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3 lg:gap-5">
            {MARKET_FEATURES.map(({ key, icon, href, wide }) => (
              <li key={key} className={cn(wide && "lg:col-span-2")}>
                <Tile className={cn(wide && "bg-gradient-to-br from-primary/10 via-card to-card")}>
                  <IconBadge icon={icon} />
                  <h3 className="text-lg font-semibold text-mono">{t(`home.markets.features.${key}.title`)}</h3>
                  <p className="grow text-sm text-secondary-foreground">{t(`home.markets.features.${key}.body`)}</p>
                  <Link
                    href={href}
                    className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-primary after:absolute after:inset-0 after:rounded-2xl hover:underline"
                  >
                    {t(`home.markets.features.${key}.cta`)}
                    <ArrowRight className="size-4 rtl:rotate-180" aria-hidden="true" />
                  </Link>
                </Tile>
              </li>
            ))}
            <li>
              <Tile className="justify-center border-dashed bg-transparent">
                <IconBadge icon={Eye} />
                <p className="text-sm font-medium text-mono">{t("home.markets.watch")}</p>
              </Tile>
            </li>
          </ul>
        </div>
      </section>

      {/* My money: Zakat gets the large tile, the rest fill the grid. */}
      <section aria-labelledby="money-title" className="container py-16 lg:py-24">
        <SectionHeading id="money-title" eyebrow={t("home.money.eyebrow")} title={t("home.money.title")} lead={t("home.money.lead")} />
        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4 lg:gap-5">
          <div className="md:col-span-2 lg:row-span-2">
            <Tile className="justify-between overflow-hidden bg-brand-navy text-white">
              <div aria-hidden="true" className="absolute -end-16 -top-16 size-56 rounded-full bg-brand-teal/25 blur-3xl" />
              <div className="relative flex flex-col gap-3">
                <IconBadge icon={HandHeart} className="bg-white/10 text-brand-teal" />
                <h3 className="font-display text-2xl font-semibold">{t("home.money.features.zakat.title")}</h3>
                <p className="text-sm text-white/75">{t("home.money.features.zakat.body")}</p>
              </div>
              <ul className="relative mt-4 flex flex-wrap gap-2">
                {ZAKAT_COUNTED.map((kind) => (
                  <li key={kind} className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/85">
                    <Check className="size-3.5 text-brand-teal" aria-hidden="true" />
                    {t(`personal.enum.assetClass.${kind}`)}
                  </li>
                ))}
              </ul>
            </Tile>
          </div>
          {MONEY_FEATURES.map(({ key, icon }) => (
            <Tile key={key}>
              <IconBadge icon={icon} />
              <h3 className="font-semibold text-mono">{t(`home.money.features.${key}.title`)}</h3>
              <p className="text-sm text-secondary-foreground">{t(`home.money.features.${key}.body`)}</p>
            </Tile>
          ))}
          <Tile className="items-start justify-center border-dashed bg-transparent">
            <Button asChild>
              <Link href={signedIn ? "/personal" : "/signup"}>
                {signedIn ? t("home.hero.ctaMyMoney") : t("home.hero.ctaSignUp")}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
          </Tile>
        </div>
      </section>

      {/* Three steps, joined by a line on wide screens. */}
      <section aria-labelledby="steps-title" className="border-y border-border bg-muted/40 py-16 lg:py-24">
        <div className="container">
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
        </div>
      </section>

      {/* Principles. */}
      <section aria-labelledby="trust-title" className="container py-16 lg:py-24">
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
      </section>

      {/* Questions and answers, readable without scripts. */}
      <section aria-labelledby="faq-title" className="border-t border-border bg-muted/40 py-16 lg:py-24">
        <div className="container max-w-3xl">
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
        </div>
      </section>

      {/* Closing call to action. */}
      <section aria-labelledby="final-title" className="container py-16 lg:py-24">
        <div className="relative isolate overflow-hidden rounded-3xl bg-brand-navy px-6 py-14 text-center text-white sm:px-12">
          <div aria-hidden="true" className="absolute -top-24 start-1/2 -z-10 size-96 -translate-x-1/2 rounded-full bg-brand-teal/25 blur-3xl" />
          <Languages className="mx-auto size-8 text-brand-teal" aria-hidden="true" />
          <h2 id="final-title" className="mt-4 font-display text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            {t("home.final.title")}
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-white/75">{t("home.final.lead")}</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild className="bg-brand-teal text-brand-navy hover:bg-brand-teal/90">
              <Link href={signedIn ? "/personal" : "/signup"}>
                {signedIn ? t("home.hero.ctaMyMoney") : t("home.hero.ctaSignUp")}
                <ArrowRight className="rtl:rotate-180" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white">
              <Link href="/shariah">{t("home.hero.ctaExplore")}</Link>
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
