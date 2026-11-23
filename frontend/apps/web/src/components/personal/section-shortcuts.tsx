/**
 * Every "My money" section as cards, grouped by task, for the overview page. It makes the
 * whole area visible at once, so a new user does not have to explore menus to find it.
 */
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SECTION_GROUPS, UTILITY_SECTIONS } from "@/lib/personal-sections";

import { Panel } from "./display";

export async function SectionShortcuts() {
  const t = await getTranslations("personal");
  const groups = [
    ...SECTION_GROUPS.filter((g) => g.key !== "overview").map((g) => ({
      key: g.key,
      title: t(`nav.groups.${g.key}`),
      sections: g.sections,
    })),
    { key: "settings", title: t("nav.groups.settings"), sections: UTILITY_SECTIONS },
  ];
  return (
    <Panel title={t("nav.allSections")} description={t("nav.shortcutsIntro")}>
      <div className="grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
        {groups.map((group) => (
          <section key={group.key} className="flex flex-col gap-1">
            <h3 className="px-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</h3>
            {group.sections.map((s) => {
              const Icon = s.icon;
              return (
                <Link
                  key={s.key}
                  href={s.href}
                  className="group/row flex items-start gap-3 rounded-lg p-2.5 hover:bg-accent/60 focus-visible:bg-accent/60"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground group-hover/row:text-primary">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <span className="flex flex-col">
                    <span className="text-sm font-medium text-mono">{t(`sections.${s.key}`)}</span>
                    <span className="text-xs text-muted-foreground">{t(`nav.describe.${s.key}`)}</span>
                  </span>
                </Link>
              );
            })}
          </section>
        ))}
      </div>
    </Panel>
  );
}
