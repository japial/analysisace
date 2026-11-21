/** Watch or stop watching a company (FR7.1). Visitors get a sign-in link instead. */
import type { WatchItem } from "@analysisace/core";
import { Eye, EyeOff } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { setWatchAction } from "@/app/actions/market";
import { ActionButton } from "@/components/personal/forms";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { request } from "@/lib/api";
import { optionalToken } from "@/lib/market";

export async function WatchButton({ ticker }: { ticker: string }) {
  const t = await getTranslations("market.watch");
  const token = await optionalToken();
  if (!token) {
    return (
      <Button variant="outline" size="sm" asChild>
        <Link href={{ pathname: "/signin", query: { next: `/companies/${ticker}` } }}>
          <Eye />
          {t("signIn")}
        </Link>
      </Button>
    );
  }
  const items = await request<WatchItem[]>("/watchlist", { token }).catch(() => [] as WatchItem[]);
  const watching = items.some((i) => i.ticker === ticker);
  return (
    <span className="inline-flex flex-wrap items-center gap-2" title={watching ? t("watching") : undefined}>
      <ActionButton action={setWatchAction.bind(null, ticker, !watching)}>
        {watching ? <EyeOff /> : <Eye />}
        {watching ? t("unwatch") : t("watch")}
      </ActionButton>
    </span>
  );
}
