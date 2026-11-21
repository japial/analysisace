import type { Envelope, MacroNote, MacroNoteSummary } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { NoteBody, NoteFigures } from "@/components/market/note";
import { MarketShell } from "@/components/market/shell";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { Link } from "@/i18n/navigation";
import { loadPublic, marketSetup } from "@/lib/market";

interface Props {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "market.macro" });
  return { title: t("metaTitle"), description: t("intro") };
}

/** F4: the newest published note in the page language, and the archive. */
export default async function MacroPage({ params }: Props) {
  const { locale } = await params;
  const { t, f } = await marketSetup(locale);
  const lang = locale === "bn" ? "bn" : "en";
  const notes = await loadPublic<MacroNoteSummary[]>(`/macro/notes?locale=${lang}`);
  const newest = notes.ok ? notes.data[0] : undefined;
  const latest = newest ? await loadPublic<Envelope<MacroNote>>(`/macro/notes/${newest.week_start}?locale=${lang}`) : null;

  return (
    <MarketShell title={t("market.macro.title")} description={t("market.macro.intro")}>
      {!notes.ok ? (
        <LoadError code={notes.code} />
      ) : !newest || !latest ? (
        <Panel title={t("market.macro.latest")}>
          <Empty>{t("market.macro.empty")}</Empty>
        </Panel>
      ) : !latest.ok ? (
        <LoadError code={latest.code} />
      ) : (
        <>
          <Panel
            title={latest.data.data.title}
            description={t("market.macro.week", { date: f.date(latest.data.data.week_start) })}
          >
            <NoteBody body={latest.data.data.body} />
          </Panel>
          <Panel
            title={t("market.macro.figuresTitle")}
            table
            footnote={{ asOf: latest.data.as_of, sources: latest.data.sources }}
          >
            <NoteFigures note={latest.data.data} />
          </Panel>
          {notes.data.length > 1 && (
            <Panel title={t("market.macro.archive")}>
              <ul className="flex flex-col gap-2 text-sm">
                {notes.data.slice(1).map((n) => (
                  <li key={n.id} className="flex flex-wrap items-baseline gap-x-3">
                    <span className="tabular-nums text-muted-foreground">{f.date(n.week_start)}</span>
                    <Link href={`/macro/${n.week_start}`} className="text-primary hover:underline">
                      {n.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </>
      )}
    </MarketShell>
  );
}
