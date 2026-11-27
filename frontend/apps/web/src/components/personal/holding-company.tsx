/**
 * "About this company" on a holding with a DSE ticker: the shares you own lead to the stock
 * tools, instead of the tools being the way in (D19). Shows the company's Shariah status and
 * its rate sensitivity from the public market endpoints, and links to the company page.
 * History only; nothing here tells anyone to buy, sell or hold.
 */
import type { CompanyShariah, Envelope, Score } from "@analysisace/core";
import { ArrowRight } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import { loadPublic } from "@/lib/market";

import { Facts, Panel, ShariahBadge } from "./display";

export async function HoldingCompanyPanel({ ticker, locale }: { ticker: string; locale: string }) {
  const t = await getTranslations();
  const f = formatterFor(locale);
  const code = encodeURIComponent(ticker.toUpperCase());
  const [shariah, scores] = await Promise.all([
    loadPublic<Envelope<CompanyShariah>>(`/companies/${code}/shariah`),
    loadPublic<Envelope<Score[]>>(`/companies/${code}/scores`),
  ]);
  const rate = scores.ok
    ? scores.data.data.find((s) => s.subject_type === "TICKER" && s.score_type === "RATE_SENSITIVITY")
    : undefined;
  const footnote = shariah.ok ? { asOf: shariah.data.as_of, sources: shariah.data.sources } : undefined;

  return (
    <Panel
      title={t("personal.holdingCompany.title")}
      description={t("personal.holdingCompany.intro")}
      actions={
        <Button variant="outline" size="sm" asChild>
          <Link href={`/companies/${code}`}>
            {t("personal.holdingCompany.open", { ticker: ticker.toUpperCase() })}
            <ArrowRight className="rtl:rotate-180" />
          </Link>
        </Button>
      }
      footnote={footnote}
    >
      <Facts
        items={[
          {
            label: t("personal.shariah"),
            value: shariah.ok ? <ShariahBadge status={shariah.data.data.status} /> : t("personal.holdingCompany.notScreened"),
          },
          {
            label: t("market.scores.title"),
            value:
              rate && rate.value !== null
                ? `${f.pct(rate.value, 2, true)} · ${t(`market.scores.confidence.${rate.confidence}`)}`
                : t("market.scores.none"),
          },
        ]}
      />
      {rate && rate.value !== null && (
        <p className="mt-3 text-xs text-muted-foreground">{t("personal.holdingCompany.rateHint")}</p>
      )}
    </Panel>
  );
}
