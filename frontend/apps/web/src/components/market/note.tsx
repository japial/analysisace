/**
 * A weekly macro note (F4): its text and its figure table. The text is plain lines:
 * "## " starts a heading, "- " a list item; anything else is a paragraph. No HTML is rendered.
 */
import type { MacroNote } from "@analysisace/core";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatterFor } from "@/lib/fmt";
import { seriesLabel } from "@/lib/market-labels";

export function NoteBody({ body }: { body: string }) {
  const blocks: ReactNode[] = [];
  let items: string[] = [];
  const flush = () => {
    if (items.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc ps-5">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>,
      );
      items = [];
    }
  };
  for (const raw of body.split("\n")) {
    const line = raw.trim();
    if (line.startsWith("- ")) {
      items.push(line.slice(2));
      continue;
    }
    flush();
    if (!line) continue;
    if (line.startsWith("## ")) {
      blocks.push(
        <h3 key={`h-${blocks.length}`} className="text-base font-semibold text-mono">
          {line.slice(3)}
        </h3>,
      );
    } else {
      blocks.push(<p key={`p-${blocks.length}`}>{line}</p>);
    }
  }
  flush();
  return <div className="flex flex-col gap-3 text-sm leading-relaxed text-secondary-foreground">{blocks}</div>;
}

export async function NoteFigures({ note }: { note: MacroNote }) {
  const t = await getTranslations();
  const f = formatterFor(await getLocale());
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("market.macro.figure")}</TableHead>
          <TableHead className="text-end">{t("market.macro.value")}</TableHead>
          <TableHead className="text-end">{t("market.macro.change")}</TableHead>
          <TableHead className="hidden md:table-cell">{t("market.macro.asOf")}</TableHead>
          <TableHead className="hidden lg:table-cell">{t("market.macro.source")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {note.figures.map((fig) => (
          <TableRow key={fig.code}>
            <TableCell>{seriesLabel(t, fig.code)}</TableCell>
            <TableCell className="text-end tabular-nums">
              {fig.unit === "pct" ? f.pct(fig.value) : f.num(fig.value, 2)}
            </TableCell>
            <TableCell className="text-end tabular-nums">
              {fig.kind === "index" || fig.unit !== "pct" ? f.pct(fig.change_pct, 2, true) : f.num(fig.change, 2)}
            </TableCell>
            <TableCell className="hidden text-secondary-foreground md:table-cell">{f.date(fig.as_of)}</TableCell>
            <TableCell className="hidden text-secondary-foreground lg:table-cell">
              {fig.source_url ? (
                <a href={fig.source_url} rel="noopener" className="underline">
                  {fig.source_name}
                </a>
              ) : (
                fig.source_name
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
