import { ALERT_TYPES, type AlertRule, type Notifications } from "@analysisace/core";
import { ArrowRight } from "lucide-react";

import { markNotificationsReadAction, setAlertRuleAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Empty, LoadError, Panel } from "@/components/personal/display";
import { ActionButton, ActionForm, CheckField, SelectField } from "@/components/personal/forms";
import { PersonalShell } from "@/components/personal/shell";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/navigation";
import { regimeLabel, statusLabel } from "@/lib/market-labels";
import { get, load } from "@/lib/personal";
import { type PageProps, enumLabel, sectionMetadata, setup } from "@/lib/personal-page";

export const generateMetadata = sectionMetadata("alerts");

/** Settings that take a number, with the key the API stores it under. */
const ALERT_PARAMS: Partial<Record<string, string>> = {
  VOLATILITY: "max_volatility_pct",
};

/** Notifications and alert settings (F20). Emails are logged until a provider is chosen. */
export default async function AlertsPage({ params }: PageProps) {
  const { locale } = await params;
  const { ctx, t, f } = await setup(locale, "/personal/alerts");
  const title = t("personal.sections.alerts");

  const [notices, rules] = await Promise.all([
    load(get<Notifications>(ctx, "/notifications?limit=50")),
    load(get<AlertRule[]>(ctx, "/alerts")),
  ]);

  /** The notice text, filled in from the values the job stored with it. */
  const message = (key: string, data: Record<string, string | number | null>) => {
    // A monthly report with income recorded (FR27.6) has a fuller text; older ones do not.
    const variant = key === "MONTHLY_REPORT" && data.income != null ? "MONTHLY_REPORT_INCOME" : key;
    const path = `personal.notice.${variant}`;
    if (!t.has(path as never)) return enumLabel(t, "alertType", key);
    const values = Object.fromEntries(
      Object.entries(data).map(([k, v]) => {
        if (v === null) return [k, "—"];
        if (k === "date" && typeof v === "string") return [k, f.date(v)];
        if (/(amount|spending|net_worth|zakat_due|income|savings)$/.test(k) && typeof v === "string") return [k, f.bdt(v)];
        if (k === "month" && typeof v === "string") return [k, f.month(v.length === 7 ? `${v}-01` : v)];
        if (k === "asset_class" && typeof v === "string") return [k, enumLabel(t, "assetClass", v)];
        // Market alerts (F7) store codes; show them as words in the reader's language.
        if ((k === "from_status" || k === "to_status") && typeof v === "string") return [k, statusLabel(t, v)];
        if ((k === "label" || k === "previous") && typeof v === "string") return [k, regimeLabel(t, v)];
        if (k === "title_en" && locale === "bn" && typeof data.title_bn === "string") return [k, data.title_bn];
        return [k, String(v)];
      }),
    );
    return t(path as never, values as never);
  };

  return (
    <PersonalShell ctx={ctx} title={title} description={t("personal.alerts.intro")}>
      <Panel
        title={t("personal.alerts.notices")}
        actions={
          notices.ok &&
          notices.data.unread > 0 && (
            <ActionButton action={markNotificationsReadAction.bind(null, undefined)}>{t("personal.alerts.markAllRead")}</ActionButton>
          )
        }
      >
        {!notices.ok ? (
          <LoadError code={notices.code} />
        ) : notices.data.items.length === 0 ? (
          <Empty>{t("personal.alerts.noNotices")}</Empty>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {notices.data.items.map((n) => (
              <li key={n.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="flex flex-col gap-0.5 text-sm">
                  <p className="flex items-center gap-2 font-medium text-mono">
                    {!n.read_at && (
                      <Badge variant="primary" appearance="light" size="sm">{t("personal.alerts.new")}</Badge>
                    )}
                    {enumLabel(t, "alertType", n.type)}
                  </p>
                  <p className="text-secondary-foreground">{message(n.message_key, n.data)}</p>
                  <p className="text-xs text-muted-foreground">{f.date(n.created_at, true)}</p>
                </div>
                <div className="flex items-center gap-2">
                  {n.link?.startsWith("/") && !n.link.startsWith("//") && (
                    <Link href={n.link} className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                      {t("personal.alerts.open")}
                      <ArrowRight className="size-3.5" />
                    </Link>
                  )}
                  {!n.read_at && (
                    <ActionButton action={markNotificationsReadAction.bind(null, n.id)} variant="ghost">
                      {t("personal.alerts.markRead")}
                    </ActionButton>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={t("personal.alerts.settings")} description={t("personal.alerts.settingsIntro")}>
        {!rules.ok ? (
          <LoadError code={rules.code} />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {ALERT_TYPES.map((type) => {
              const rule = rules.data.find((r) => r.type === type);
              const param = ALERT_PARAMS[type];
              return (
                <li key={type} className="py-4">
                  <ActionForm
                    action={setAlertRuleAction.bind(null, type)}
                    submitLabel={t("common.save")}
                    success={t("common.saved")}
                    reset={false}
                    className="gap-3"
                  >
                    <div>
                      <p className="font-medium text-mono">{enumLabel(t, "alertType", type)}</p>
                      <p className="text-sm text-muted-foreground">{t(`personal.alerts.describe.${type}`)}</p>
                    </div>
                    <div className="flex flex-wrap items-end gap-4">
                      <CheckField label={t("personal.alerts.on")} name="is_active" defaultChecked={rule?.is_active ?? true} />
                      <SelectField
                        label={t("personal.alerts.channel")}
                        name="channel"
                        options={["EMAIL", "PUSH", "BOTH"].map((v) => ({ value: v, label: enumLabel(t, "channel", v) }))}
                        defaultValue={rule?.channel ?? "EMAIL"}
                        className="w-40"
                      />
                      <SelectField
                        label={t("personal.alerts.frequency")}
                        name="frequency"
                        options={["INSTANT", "DAILY_DIGEST"].map((v) => ({ value: v, label: enumLabel(t, "alertFrequency", v) }))}
                        defaultValue={rule?.frequency ?? "DAILY_DIGEST"}
                        className="w-44"
                      />
                      {param && (
                        <div className="w-44">
                          <Field
                            label={t(`personal.alerts.param.${param}` as "personal.alerts.param.max_volatility_pct")}
                            name={`param_${param}`}
                            id={`param-${type}`}
                            type="number"
                            inputMode="decimal"
                            min="0"
                            step="0.1"
                            defaultValue={rule?.params?.[param] !== undefined ? String(rule.params[param]) : ""}
                          />
                        </div>
                      )}
                    </div>
                  </ActionForm>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </PersonalShell>
  );
}
