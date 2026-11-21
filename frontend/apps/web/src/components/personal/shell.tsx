/**
 * Frame for every personal finance page: toolbar, the household switcher, the content and
 * the required disclaimer. Pages without a household get the "create a household" card.
 */
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { createHouseholdAction, switchHouseholdAction } from "@/app/actions/personal";
import { Field } from "@/components/form/form-parts";
import { Disclaimer } from "@/components/disclaimer";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import type { PersonalContext } from "@/lib/personal";

import { ActionButton, ActionForm } from "./forms";
import { Panel } from "./display";

interface Props {
  ctx: PersonalContext;
  title: string;
  description?: string;
  /** Breadcrumbs between "My money" and this page. */
  trail?: { label: string; href?: string }[];
  actions?: ReactNode;
  /** The overview page itself: no "My money" crumb. */
  root?: boolean;
  children: ReactNode;
}

export async function PersonalShell({
  ctx,
  title,
  description,
  trail = [],
  actions,
  root = false,
  children,
}: Props) {
  const t = await getTranslations();
  const crumbs = [
    { label: t("nav.home"), href: "/" },
    ...(root ? [] : [{ label: t("nav.personal"), href: "/personal" }]),
    ...trail,
    { label: title },
  ];

  return (
    <>
      <Toolbar title={title} description={description} breadcrumbs={crumbs}>
        {ctx.household && (
          <div className="flex flex-wrap items-center gap-2" data-print="hide">
            <Badge variant="secondary" appearance="light">
              {ctx.household.name} · {t(`personal.enum.householdRole.${ctx.household.role}`)}
            </Badge>
            {ctx.households
              .filter((h) => h.id !== ctx.household?.id)
              .map((h) => (
                <ActionButton key={h.id} action={switchHouseholdAction.bind(null, h.id)} variant="ghost">
                  {t("personal.switchTo", { name: h.name })}
                </ActionButton>
              ))}
            {actions}
          </div>
        )}
      </Toolbar>
      <div className="container flex flex-col gap-5 pb-10 lg:gap-7.5">
        {ctx.household ? children : <NoHousehold />}
        <Disclaimer />
      </div>
    </>
  );
}

async function NoHousehold() {
  const t = await getTranslations("personal.household");
  return (
    <Panel title={t("createTitle")} description={t("createIntro")}>
      <ActionForm action={createHouseholdAction} submitLabel={t("create")} className="max-w-md">
        <Field label={t("name")} name="name" maxLength={120} required placeholder={t("namePlaceholder")} />
      </ActionForm>
    </Panel>
  );
}
