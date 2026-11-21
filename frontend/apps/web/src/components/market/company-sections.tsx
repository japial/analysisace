/**
 * Market blocks on a company page: the Shariah screen (F1), rate sensitivity (F3) and how
 * the stock moved around past shocks (F5). Server components; every figure comes from the API.
 */
import type { CompanyEvent, CompanyShariah, Envelope, Score } from "@analysisace/core";
import { getLocale, getTranslations } from "next-intl/server";

import { Empty, Facts, LoadError, Panel, ShariahBadge } from "@/components/personal/display";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatterFor } from "@/lib/fmt";
import type { Loaded } from "@/lib/market";
import { methodLabel, ruleLabel, statusLabel } from "@/lib/market-labels";


export async function ShariahSection({ result }: { result: Loaded<Envelope<CompanyShariah>> }) {
  const t = await getTranslations();
  const f = formatterFor(await getLocale());
  if (!result.ok) {
    return (
      <Panel title={t("market.screen.title")}>
        {result.status === 404 ? <Empty>{t("market.screen.notScreened")}</Empty> : <LoadError code={result.code} />}
      </Panel>
    );
  }
  const data = result.data.data;
  const fin = data.financials;
  const activity = data.classification?.activity;

  return (
    <Panel
      title={t("market.screen.title")}
      actions={<ShariahBadge status={data.status} />}
      footnote={{ asOf: result.data.as_of, sources: result.data.sources }}
    >
      <div className="flex flex-col gap-6">
        <Facts
          items={[
            { label: t("market.screen.shown"), value: statusLabel(t, data.status) },
            { label: t("market.screen.lastScreened"), value: f.date(data.screened_at) },
            { label: t("market.screen.methodVersion"), value: `${methodLabel(t, data.method)} · ${data.method_version}` },
          ]}
        />
        <div className="flex flex-col gap-1 text-sm text-secondary-foreground">
          <p>{t("market.screen.defaultMethod", { method: methodLabel(t, data.method) })}</p>
          {data.override_status && (
            <p className="text-mono">
              {t("market.screen.override", { reason: data.override_reason ?? "" })}{" "}
              {t("market.screen.screenSaid", { status: statusLabel(t, data.screen_status) })}
            </p>
          )}
          {!data.config_approved && <p>{t("market.shariah.provisional")}</p>}
        </div>

        {data.board_note && (
          <div className="rounded-lg border border-border p-4 text-sm">
            <p className="font-medium text-mono">{t("market.screen.boardNote")}</p>
            <p className="mt-1 whitespace-pre-line text-secondary-foreground">{data.board_note}</p>
          </div>
        )}

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-mono">{t("market.screen.stage1Title")}</h3>
          <p className="text-sm text-secondary-foreground">
            {!data.classification
              ? t("market.screen.stage1None")
              : data.classification.stage1_pass
                ? t("market.screen.stage1Pass")
                : t("market.screen.stage1Fail", {
                    activity: activity && t.has(`market.screen.activity.${activity}` as never) ? t(`market.screen.activity.${activity}` as never) : (activity ?? ""),
                  })}
          </p>
          {data.classification?.reason && (
            <p className="text-sm text-muted-foreground" lang="en">
              {data.classification.reason}
            </p>
          )}
        </section>

        {data.results.map((r) => {
          const cap = r.ratios.find((x) => x.rule === "market_cap_average");
          const rules = r.ratios.filter((x) => x.rule !== "market_cap_average");
          return (
            <section key={r.id} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-mono">
                  {t("market.screen.rulesTitle", { method: methodLabel(t, r.method) })}
                </h3>
                <ShariahBadge status={r.status} />
              </div>
              <p className="text-xs text-muted-foreground">{t("market.screen.period", { date: f.date(r.period_end) })}</p>
              {rules.length > 0 && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("market.screen.rule")}</TableHead>
                        <TableHead className="text-end">{t("market.screen.value")}</TableHead>
                        <TableHead className="text-end">{t("market.screen.threshold")}</TableHead>
                        <TableHead>{t("market.screen.result")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rules.map((rule) => (
                        <TableRow key={rule.rule}>
                          <TableCell className="text-sm">{ruleLabel(t, rule.rule)}</TableCell>
                          <TableCell className="text-end tabular-nums">
                            {rule.value_pct == null ? t("market.screen.missing") : f.pct(rule.value_pct)}
                          </TableCell>
                          <TableCell className="text-end tabular-nums">
                            {t("market.screen.below", { value: f.pct(rule.threshold_pct) })}
                          </TableCell>
                          <TableCell>
                            {rule.passed == null ? (
                              <Badge variant="secondary" appearance="light" size="sm">{t("market.screen.missing")}</Badge>
                            ) : rule.note === "WITHIN_REVIEW_MARGIN" ? (
                              <Badge variant="warning" appearance="light" size="sm">{t("market.screen.review")}</Badge>
                            ) : rule.passed ? (
                              <Badge variant="success" appearance="light" size="sm">{t("market.screen.pass")}</Badge>
                            ) : (
                              <Badge variant="destructive" appearance="light" size="sm">{t("market.screen.fail")}</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              {cap?.value && (
                <p className="text-xs text-muted-foreground">
                  {t("market.screen.marketCap", { months: cap.months ?? 0, value: f.compact(cap.value) })}
                </p>
              )}
            </section>
          );
        })}

        {fin && (
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-mono">{t("market.screen.financialsTitle")}</h3>
            <Facts
              items={[
                ...(
                  [
                    "total_debt_interest_bearing",
                    "cash_and_interest_securities",
                    "receivables",
                    "total_revenue",
                    "non_permissible_income",
                  ] as const
                ).map((key) => ({
                  label: t(`market.screen.figures.${key}`),
                  value: fin[key] === null ? t("market.screen.missing") : f.compact(fin[key]),
                })),
                { label: t("market.screen.shares"), value: f.num(fin.shares_outstanding === null ? null : String(fin.shares_outstanding), 0) },
              ]}
            />
            <p className="text-xs text-muted-foreground">
              {t("market.screen.source")}:{" "}
              {fin.source_url ? (
                <a href={fin.source_url} rel="noopener" className="underline hover:text-mono">
                  {fin.source_name}
                </a>
              ) : (
                fin.source_name
              )}
              {fin.source_page !== null && ` · ${t("market.screen.page", { page: fin.source_page })}`}
            </p>
          </section>
        )}

        {data.history.length > 0 && (
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-mono">{t("market.screen.historyTitle")}</h3>
            <ul className="flex flex-col gap-1.5 text-sm">
              {data.history.map((h) => (
                <li key={h.changed_at + h.to_status} className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
                  <span className="tabular-nums text-muted-foreground">{f.date(h.changed_at)}</span>
                  <span className="text-mono">
                    {h.from_status
                      ? t("market.screen.changed", { from: statusLabel(t, h.from_status), to: statusLabel(t, h.to_status) })
                      : t("market.screen.first", { to: statusLabel(t, h.to_status) })}
                  </span>
                  <Badge variant="secondary" appearance="light" size="sm">
                    {t(`market.screen.cause.${h.cause}`)}
                  </Badge>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </Panel>
  );
}

export async function ScoresSection({ result }: { result: Loaded<Envelope<Score[]>> }) {
  const t = await getTranslations();
  const f = formatterFor(await getLocale());
  if (!result.ok) {
    return (
      <Panel title={t("market.scores.title")}>
        <LoadError code={result.code} />
      </Panel>
    );
  }
  const rows = result.data.data;
  const groups = (["TICKER", "SECTOR"] as const)
    .map((type) => ({ type, rows: rows.filter((r) => r.subject_type === type) }))
    .filter((g) => g.rows.length > 0);

  return (
    <Panel
      title={t("market.scores.title")}
      description={t("market.scores.intro")}
      footnote={{ asOf: result.data.as_of, sources: result.data.sources }}
    >
      {groups.length === 0 ? (
        <Empty>{t("market.scores.none")}</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {groups.map((group) => {
            const main = group.rows.find((r) => r.score_type === "RATE_SENSITIVITY");
            const plain = group.rows.find((r) => r.score_type === "RATE_SENSITIVITY_NO_MARKET");
            const subject = group.rows[0]?.subject ?? "";
            return (
              <div key={group.type} className="flex flex-col gap-2 rounded-xl border border-border p-4">
                <p className="text-sm text-muted-foreground">
                  {group.type === "TICKER" ? t("market.scores.stock") : t("market.scores.sector", { name: subject })}
                </p>
                {main && main.value !== null ? (
                  <>
                    <p className="text-2xl font-semibold tabular-nums text-mono">{f.pct(main.value, 2, true)}</p>
                    <p className="text-xs text-muted-foreground">{t("market.scores.value")} · {t("market.scores.withMarket")}</p>
                    <Badge variant="secondary" appearance="light" size="sm" className="self-start">
                      {t(`market.scores.confidence.${main.confidence}`)}
                    </Badge>
                    {plain?.value != null && (
                      <p className="text-sm text-secondary-foreground">
                        {t("market.scores.withoutMarket")}: <span className="tabular-nums">{f.pct(plain.value, 2, true)}</span>
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {t("market.scores.sample", {
                        start: f.date(main.sample_start),
                        end: f.date(main.sample_end),
                        n: f.num(String(main.n_obs), 0),
                      })}
                      {" · "}
                      {t("market.scores.tStat")}: {f.num(main.t_stat)}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-secondary-foreground">{t("market.scores.insufficient")}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

export async function CompanyEventsSection({ result }: { result: Loaded<Envelope<CompanyEvent[]>> }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const f = formatterFor(locale);
  if (!result.ok) {
    return (
      <Panel title={t("market.events.companyTitle")}>
        <LoadError code={result.code} />
      </Panel>
    );
  }
  const rows = result.data.data;
  return (
    <Panel
      title={t("market.events.companyTitle")}
      table={rows.length > 0}
      footnote={{ asOf: result.data.as_of, sources: result.data.sources }}
    >
      {rows.length === 0 ? (
        <Empty>{t("market.events.companyEmpty")}</Empty>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("market.events.title")}</TableHead>
              <TableHead className="text-end">{t("market.events.ret1")}</TableHead>
              <TableHead className="hidden text-end sm:table-cell">{t("market.events.ret5")}</TableHead>
              <TableHead className="text-end">{t("market.events.ret20")}</TableHead>
              <TableHead className="hidden text-end md:table-cell">{t("market.events.maxDd")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ event, metric }) => (
              <TableRow key={event.id}>
                <TableCell>
                  <Link href={`/events/${event.slug}`} className="text-primary hover:underline">
                    {locale === "bn" ? event.title_bn : event.title_en}
                  </Link>
                  <span className="block text-xs text-muted-foreground">{f.date(event.t0)}</span>
                </TableCell>
                <TableCell className="text-end tabular-nums">{f.pct(metric.ret_1, 2, true)}</TableCell>
                <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(metric.ret_5, 2, true)}</TableCell>
                <TableCell className="text-end tabular-nums">{f.pct(metric.ret_20, 2, true)}</TableCell>
                <TableCell className="hidden text-end tabular-nums md:table-cell">{f.pct(metric.max_dd_60, 2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Panel>
  );
}
