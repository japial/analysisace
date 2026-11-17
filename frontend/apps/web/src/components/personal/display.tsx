/**
 * Display pieces shared by the personal finance pages. Server components; no state.
 */
import type { SourceRef } from "@analysisace/core";
import { CircleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { DataFootnote } from "@/components/data-footnote";
import { Alert, AlertDescription, AlertIcon } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTable, CardTitle } from "@/components/ui/card";
import type { ErrorCode } from "@/lib/form-state";
import { cn } from "@/lib/utils";

/** A card with a title, optional buttons on the right, and either content or a table. */
export function Panel({
  title,
  description,
  actions,
  children,
  table = false,
  footnote,
  className,
  id,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  /** Put a table edge to edge instead of in padded content. */
  table?: boolean;
  footnote?: { asOf: string | null; sources: SourceRef[] };
  className?: string;
  id?: string;
}) {
  return (
    <Card className={className} id={id}>
      <CardHeader className="py-3.5">
        <div className="flex flex-col gap-0.5">
          <CardTitle>{title}</CardTitle>
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </CardHeader>
      {table ? <CardTable>{children}</CardTable> : <CardContent>{children}</CardContent>}
      {footnote && (
        <div className="border-t border-border px-5 py-3">
          <DataFootnote asOf={footnote.asOf} sources={footnote.sources} />
        </div>
      )}
    </Card>
  );
}

/** A headline figure. */
export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span
        className={cn(
          "text-xl font-semibold text-mono tabular-nums",
          tone === "negative" && "text-destructive",
        )}
      >
        {value}
      </span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

/**
 * Horizontal bars for shares of a whole. Each row gives its own percentage from the API;
 * the bar width uses it directly.
 */
export function ShareBars({
  rows,
}: {
  rows: { key: string; label: string; value: string; pct: string; pctText: string }[];
}) {
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((row) => (
        <li key={row.key} className="flex flex-col gap-1">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-mono">{row.label}</span>
            <span className="text-secondary-foreground tabular-nums">
              {row.value} · {row.pctText}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `min(100%, ${row.pct}%)` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Shown in place of a block whose data could not be loaded. */
export function LoadError({ code }: { code: ErrorCode }) {
  const t = useTranslations("errors");
  return (
    <Alert variant="destructive" appearance="light" role="alert">
      <AlertIcon>
        <CircleAlert />
      </AlertIcon>
      <AlertDescription>{t.has(code) ? t(code) : t("UNAVAILABLE")}</AlertDescription>
    </Alert>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

const SHARIAH_VARIANT = {
  COMPLIANT: "success",
  NON_COMPLIANT: "destructive",
  UNKNOWN: "secondary",
  UNDER_REVIEW: "warning",
} as const;

/** Shariah status of a holding, with a word as well as a colour. */
export function ShariahBadge({ status }: { status: string }) {
  const t = useTranslations("personal.enum.shariah");
  const variant = SHARIAH_VARIANT[status as keyof typeof SHARIAH_VARIANT] ?? "secondary";
  return (
    <Badge variant={variant} appearance="light" size="sm">
      {t.has(status as never) ? t(status as never) : status}
    </Badge>
  );
}

/** A definition list laid out in columns. */
export function Facts({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-0.5">
          <dt className="text-muted-foreground">{item.label}</dt>
          <dd className="text-mono">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
