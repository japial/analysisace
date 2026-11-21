import { EVENT_TYPES, type ShockEvent } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SegmentedLinks } from "@/components/market/segmented-links";
import { MarketShell } from "@/components/market/shell";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/navigation";
import { loadPublic, marketSetup, pick } from "@/lib/market";
import { eventTypeLabel } from "@/lib/market-labels";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ type?: string | string[] }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "market.events" });
  return { title: t("metaTitle"), description: t("intro") };
}

/** F5: the event library (FR5.1). */
export default async function EventsPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { t, f } = await marketSetup(locale);
  const raw = (await searchParams).type;
  const type = EVENT_TYPES.find((x) => x === (Array.isArray(raw) ? raw[0] : raw));
  const events = await loadPublic<ShockEvent[]>(`/events${type ? `?type=${type}` : ""}`);

  return (
    <MarketShell title={t("market.events.title")} description={t("market.events.intro")}>
      <SegmentedLinks
        label={t("market.events.allTypes")}
        className="self-start"
        options={[
          { key: "all", label: t("market.events.allTypes"), href: "/events", current: !type },
          ...EVENT_TYPES.map((x) => ({
            key: x,
            label: eventTypeLabel(t, x),
            href: { pathname: "/events", query: { type: x } },
            current: x === type,
          })),
        ]}
      />
      {!events.ok ? (
        <LoadError code={events.code} />
      ) : events.data.length === 0 ? (
        <Panel title={t("market.events.title")}>
          <Empty>{t("market.events.empty")}</Empty>
        </Panel>
      ) : (
        <ul className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {events.data.map((event) => (
            <li key={event.id}>
              <Panel
                title={pick(event, "title", locale)}
                actions={
                  <Badge variant="secondary" appearance="light" size="sm">
                    {eventTypeLabel(t, event.type)}
                  </Badge>
                }
                className="h-full"
              >
                <div className="flex flex-col gap-3 text-sm">
                  <p className="text-muted-foreground">
                    {t("market.events.t0")}: {f.date(event.t0)}
                  </p>
                  <p className="text-secondary-foreground">{pick(event, "description", locale)}</p>
                  <Link href={`/events/${event.slug}`} className="self-start text-primary hover:underline">
                    {t("market.events.open")}
                  </Link>
                </div>
              </Panel>
            </li>
          ))}
        </ul>
      )}
    </MarketShell>
  );
}
