import type { Member, ZakatSnapshot } from "@analysisace/core";
import { notFound } from "next/navigation";

import { deleteZakatAction } from "@/app/actions/personal";
import { Facts, Panel, Stat, StatGrid } from "@/components/personal/display";
import { DeleteButton } from "@/components/personal/forms";
import { PrintButton } from "@/components/personal/print-button";
import { PersonalShell } from "@/components/personal/shell";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { hh, load } from "@/lib/personal";
import { type PageProps, enumLabel, setup } from "@/lib/personal-page";

/** One Zakat snapshot with every line, as worked out on its date (FR13.1 to FR13.4). */
export default async function ZakatSnapshotPage({ params }: PageProps<{ id: string }>) {
  const { locale, id } = await params;
  const { ctx, t, f } = await setup(locale, `/personal/zakat/${id}`);
  const trail = [{ label: t("personal.sections.zakat"), href: "/personal/zakat" }];
  if (!ctx.household) return <PersonalShell ctx={ctx} title={t("personal.sections.zakat")}>{null}</PersonalShell>;

  let s: ZakatSnapshot;
  try {
    s = await hh<ZakatSnapshot>(ctx, `/zakat/snapshots/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const members = await load(hh<Member[]>(ctx, "/members"));
  const member = members.ok ? members.data.find((m) => m.id === s.member_id) : undefined;
  const assets = s.items.filter((i) => i.asset_kind !== "LIABILITY");
  const debts = s.items.filter((i) => i.asset_kind === "LIABILITY");

  return (
    <PersonalShell
      ctx={ctx}
      title={t("personal.zakat.snapshotTitle", { name: member?.display_name ?? "—", date: f.date(s.date) })}
      trail={trail}
      actions={
        <>
          <PrintButton label={t("personal.print")} />
          {ctx.canEdit && (
            <DeleteButton action={deleteZakatAction.bind(null, ctx.household.id, id)} label={t("personal.zakat.delete")} title={t("personal.zakat.delete")} />
          )}
        </>
      }
    >
      <StatGrid>
        <Stat label={t("personal.zakat.due")} value={f.bdt(s.zakat_due)} />
        <Stat label={t("personal.zakat.netZakatable")} value={f.bdt(s.net_zakatable)} />
        <Stat label={t("personal.zakat.nisabValue")} value={f.bdt(s.nisab_value)} hint={t("personal.zakat.nisabFrom", { basis: enumLabel(t, "nisab", s.nisab_basis), price: f.bdt(s.price_per_gram) })} />
        <Stat label={t("personal.zakat.deductions")} value={f.bdt(s.total_deductions)} />
      </StatGrid>

      <Panel title={t("personal.details")}>
        <Facts
          items={[
            { label: t("personal.date"), value: f.date(s.date) },
            { label: t("personal.zakat.sharesMethod"), value: enumLabel(t, "sharesMethod", s.shares_method) },
            { label: t("personal.zakat.totalZakatable"), value: f.bdt(s.total_zakatable) },
            { label: t("personal.zakat.rulesVersion"), value: s.config_version },
            { label: t("personal.zakat.computedAt"), value: f.date(s.created_at, true) },
          ]}
        />
      </Panel>

      <Panel title={t("personal.zakat.lines")} description={t("personal.zakat.linesIntro")} table>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("personal.name")}</TableHead>
              <TableHead className="hidden md:table-cell">{t("personal.zakat.treatment")}</TableHead>
              <TableHead className="hidden text-end sm:table-cell">{t("personal.value")}</TableHead>
              <TableHead className="hidden text-end lg:table-cell">{t("personal.zakat.share")}</TableHead>
              <TableHead className="text-end">{t("personal.zakat.zakatable")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {assets.map((item) => (
              <TableRow key={`${item.asset_kind}-${item.asset_id}`}>
                <TableCell>
                  <span className="text-mono">{item.label}</span>
                  <span className="block text-xs text-muted-foreground md:hidden">{enumLabel(t, "treatment", item.treatment)}</span>
                  {item.flags.length > 0 && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {item.flags.map((flag) => (
                        <Badge key={flag} variant="warning" appearance="light" size="sm">{enumLabel(t, "zakatFlag", flag)}</Badge>
                      ))}
                    </span>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">{enumLabel(t, "treatment", item.treatment)}</TableCell>
                <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.bdt(item.value)}</TableCell>
                <TableCell className="hidden text-end tabular-nums lg:table-cell">{f.pct(item.owner_pct, 0)}</TableCell>
                <TableCell className="text-end tabular-nums">{f.bdt(item.zakatable)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={4} className="hidden lg:table-cell">{t("personal.zakat.totalZakatable")}</TableCell>
              <TableCell className="lg:hidden">{t("personal.zakat.totalZakatable")}</TableCell>
              <TableCell className="text-end tabular-nums">{f.bdt(s.total_zakatable)}</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </Panel>

      {debts.length > 0 && (
        <Panel title={t("personal.zakat.deductions")} description={t("personal.zakat.deductionsIntro")} table>
          <Table>
            <TableBody>
              {debts.map((item) => (
                <TableRow key={item.asset_id}>
                  <TableCell>{item.label}</TableCell>
                  <TableCell className="hidden text-end tabular-nums sm:table-cell">{f.pct(item.owner_pct, 0)}</TableCell>
                  <TableCell className="text-end tabular-nums">{f.bdt(item.zakatable)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      )}
    </PersonalShell>
  );
}
