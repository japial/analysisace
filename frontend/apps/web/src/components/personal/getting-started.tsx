/**
 * "Getting started" checklist on the My money overview (D22). Each step's state comes from
 * `/setup/status`, read from the household's own records; the card is not shown once every
 * step is done.
 */
import type { SetupStatus, SetupStep } from "@analysisace/core";
import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { cn } from "@/lib/utils";

import { Panel } from "./display";

/** Where each step is done. Quick start covers the first four in one form. */
const STEP_HREF: Record<SetupStep, string> = {
  you: "/personal/setup",
  income: "/personal/income",
  costs: "/personal/costs",
  savings: "/personal/portfolio",
  plan: "/personal/fire",
};

export async function GettingStarted({ status, locale, canEdit }: { status: SetupStatus; locale: string; canEdit: boolean }) {
  if (status.complete) return null;
  const t = await getTranslations("personal.setup");
  const f = formatterFor(locale);
  const pct = Math.round((status.done / status.total) * 100);
  const quickStartUseful = status.steps.slice(0, 4).some((s) => !s.done);

  return (
    <Panel
      title={t("checklistTitle")}
      description={t("checklistIntro", { done: f.num(String(status.done), 0), total: f.num(String(status.total), 0) })}
      actions={
        canEdit && quickStartUseful ? (
          <Button size="sm" asChild>
            <Link href="/personal/setup">
              {t("openQuickStart")}
              <ArrowRight className="rtl:rotate-180" />
            </Link>
          </Button>
        ) : undefined
      }
    >
      <div
        className="mb-4 h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={t("checklistTitle")}
        aria-valuemin={0}
        aria-valuemax={status.total}
        aria-valuenow={status.done}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {status.steps.map((step) => (
          <li key={step.key}>
            <Link
              href={STEP_HREF[step.key]}
              className={cn(
                "flex h-full items-start gap-2.5 rounded-lg border border-border p-3 text-sm hover:border-primary/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                step.done && "bg-muted/50",
              )}
            >
              {step.done ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              ) : (
                <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              )}
              <span className="flex flex-col gap-0.5">
                <span className={cn("font-medium text-mono", step.done && "text-muted-foreground line-through")}>
                  {t(`steps.${step.key}.title`)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {step.done ? t("doneLabel") : t(`steps.${step.key}.body`)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
