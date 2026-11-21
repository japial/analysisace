/** Frame for the market admin screens: toolbar with an "Admin" crumb, then the content. */
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Toolbar } from "@/components/layout/toolbar";

export async function AdminShell({
  title,
  description,
  trail = [],
  children,
}: {
  title: string;
  description?: string;
  trail?: { label: string; href?: string }[];
  children: ReactNode;
}) {
  const t = await getTranslations();
  return (
    <>
      <Toolbar
        title={title}
        description={description}
        breadcrumbs={[
          { label: t("nav.home"), href: "/" },
          { label: t("adminMarket.hub.title"), href: "/admin" },
          ...trail,
          { label: title },
        ]}
      />
      <div className="container flex flex-col gap-5 pb-10 lg:gap-7.5">{children}</div>
    </>
  );
}
