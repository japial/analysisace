import type { Envelope, MacroNote } from "@analysisace/core";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NoteBody, NoteFigures } from "@/components/market/note";
import { MarketShell } from "@/components/market/shell";
import { LoadError, Panel } from "@/components/personal/display";
import { loadPublic, marketSetup } from "@/lib/market";

interface Props {
  params: Promise<{ locale: string; week: string }>;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

async function loadNote(locale: string, week: string) {
  const lang = locale === "bn" ? "bn" : "en";
  return loadPublic<Envelope<MacroNote>>(`/macro/notes/${week}?locale=${lang}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, week } = await params;
  if (!DATE.test(week)) return {};
  const note = await loadNote(locale, week);
  return note.ok ? { title: note.data.data.title } : {};
}

/** F4: one published weekly note. */
export default async function MacroNotePage({ params }: Props) {
  const { locale, week } = await params;
  if (!DATE.test(week)) notFound();
  const { t, f } = await marketSetup(locale);
  const note = await loadNote(locale, week);
  if (!note.ok && note.status === 404) notFound();
  const trail = [{ label: t("nav.macro"), href: "/macro" }];
  if (!note.ok) {
    return (
      <MarketShell title={t("market.macro.title")} trail={trail}>
        <LoadError code={note.code} />
      </MarketShell>
    );
  }
  const data = note.data.data;
  return (
    <MarketShell title={data.title} description={t("market.macro.week", { date: f.date(data.week_start) })} trail={trail}>
      <Panel title={data.title}>
        <NoteBody body={data.body} />
      </Panel>
      <Panel title={t("market.macro.figuresTitle")} table footnote={{ asOf: note.data.as_of, sources: note.data.sources }}>
        <NoteFigures note={data} />
      </Panel>
    </MarketShell>
  );
}
