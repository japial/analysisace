"use client";

/**
 * Section menu for "My money". Fifteen sections in one row of tabs were hard to scan, so
 * they are grouped by task (lib/personal-sections.ts), following Metronic Layout 9's mega
 * menu:
 *
 * - From `lg` up: a menu bar with Overview and Costs as direct links, four task groups as
 *   dropdowns (each item with an icon and a one-line description), and Alerts and Household
 *   on the right. The group holding the current page is underlined.
 * - Below `lg`: one button naming the current section; it opens a sheet listing every
 *   section by group, so nothing has to be found by scrolling sideways.
 */
import { Bell, LayoutGrid } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu";
import { Sheet, SheetBody, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Link, usePathname } from "@/i18n/navigation";
import {
  SECTION_GROUPS,
  type Section,
  type SectionGroup,
  UTILITY_SECTIONS,
  currentSection,
} from "@/lib/personal-sections";
import { cn } from "@/lib/utils";

/** Undo the menu link's own panel styling for links that sit in the bar itself. */
const LINK_RESET = "flex-row rounded-none p-0 px-1 hover:bg-transparent focus:bg-transparent focus-visible:ring-0";

/** Same look as the site menu bar: a bottom border marks where you are. */
/**
 * Open the dropdowns on click (or Enter) only. With hover opening as well, a person who
 * points at a group and then clicks it closes it again, and touch screens have no hover.
 */
const CLICK_ONLY = {
  onPointerMove: (event: { preventDefault: () => void }) => event.preventDefault(),
  onPointerLeave: (event: { preventDefault: () => void }) => event.preventDefault(),
};

const BAR_ITEM =
  "-mb-px inline-flex h-11 items-center gap-2 border-b-2 border-transparent px-1 text-sm font-medium text-secondary-foreground transition-colors hover:text-mono focus-visible:text-mono data-[here=true]:border-primary data-[here=true]:text-mono [&_svg]:size-4 [&_svg]:text-muted-foreground data-[here=true]:[&_svg]:text-primary";

function isIn(group: SectionGroup, active: Section): boolean {
  return group.sections.some((s) => s.key === active.key);
}

function SectionRow({ section, active, onPick }: { section: Section; active: boolean; onPick?: () => void }) {
  const t = useTranslations("personal");
  const Icon = section.icon;
  return (
    <Link
      href={section.href}
      onClick={onPick}
      aria-current={active ? "page" : undefined}
      className="group/row flex items-start gap-3 rounded-lg p-2.5 hover:bg-accent/60 focus-visible:bg-accent/60 aria-[current=page]:bg-primary/5"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground group-hover/row:text-primary group-aria-[current=page]/row:border-primary/30 group-aria-[current=page]/row:text-primary">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-sm font-medium text-mono">{t(`sections.${section.key}`)}</span>
        <span className="text-xs text-muted-foreground">{t(`nav.describe.${section.key}`)}</span>
      </span>
    </Link>
  );
}

export function PersonalNav({ unread = 0 }: { unread?: number }) {
  const t = useTranslations("personal");
  const pathname = usePathname();
  const active = currentSection(pathname);
  const [open, setOpen] = useState(false);
  const ActiveIcon = active.icon;

  return (
    <div className="container" data-print="hide">
      {/* Phones and tablets: the current section, and a sheet with every section. */}
      <div className="flex items-center gap-2 border-b border-border py-3 lg:hidden">
        <Button
          variant="outline"
          className="h-auto flex-1 justify-between gap-3 py-2.5"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <span className="flex min-w-0 items-center gap-2.5">
            <ActiveIcon className="size-4 text-primary" aria-hidden="true" />
            <span className="truncate font-medium text-mono">{t(`sections.${active.key}`)}</span>
          </span>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {t("nav.allSections")}
            <LayoutGrid className="size-4" aria-hidden="true" />
          </span>
        </Button>
        <Button variant="outline" mode="icon" asChild className="relative size-11">
          <Link href="/personal/alerts" aria-label={unread > 0 ? `${t("sections.alerts")}: ${t("nav.unread", { n: unread })}` : t("sections.alerts")}>
            <Bell className="size-4" aria-hidden="true" />
            {unread > 0 && (
              <span className="absolute -end-1 -top-1 flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-5 text-primary-foreground">
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </Link>
        </Button>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="bottom" className="max-h-[85vh] gap-0 rounded-t-2xl p-0">
            <SheetHeader className="border-b border-border p-4">
              <SheetTitle>{t("nav.label")}</SheetTitle>
            </SheetHeader>
            <SheetBody className="overflow-y-auto p-3">
              <nav aria-label={t("nav.label")} className="flex flex-col gap-4 pb-4">
                {SECTION_GROUPS.map((group) => (
                  <section key={group.key} className="flex flex-col gap-0.5">
                    {group.sections.length > 1 && (
                      <h3 className="px-2.5 pb-1 pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {t(`nav.groups.${group.key}`)}
                      </h3>
                    )}
                    {group.sections.map((s) => (
                      <SectionRow key={s.key} section={s} active={s.key === active.key} onPick={() => setOpen(false)} />
                    ))}
                  </section>
                ))}
                <section className="flex flex-col gap-0.5 border-t border-border pt-3">
                  {UTILITY_SECTIONS.map((s) => (
                    <SectionRow key={s.key} section={s} active={s.key === active.key} onPick={() => setOpen(false)} />
                  ))}
                </section>
              </nav>
            </SheetBody>
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop: Metronic Layout 9 style menu bar with grouped dropdowns. */}
      <div className="hidden items-center justify-between gap-6 border-b border-border lg:flex">
        <NavigationMenu viewport={false} aria-label={t("nav.label")}>
          <NavigationMenuList className="gap-6">
            {SECTION_GROUPS.map((group) => {
              const here = isIn(group, active);
              const GroupIcon = group.icon;
              if (group.sections.length === 1) {
                const section = group.sections[0]!;
                return (
                  <NavigationMenuItem key={group.key}>
                    <NavigationMenuLink asChild className={cn(LINK_RESET, BAR_ITEM)}>
                      <Link href={section.href} data-here={here || undefined} aria-current={here ? "page" : undefined}>
                        <GroupIcon aria-hidden="true" />
                        {t(`nav.groups.${group.key}`)}
                      </Link>
                    </NavigationMenuLink>
                  </NavigationMenuItem>
                );
              }
              return (
                <NavigationMenuItem key={group.key}>
                  <NavigationMenuTrigger
                    {...CLICK_ONLY}
                    data-here={here || undefined}
                    className={cn(BAR_ITEM, "h-11 rounded-none bg-transparent! py-0 hover:bg-transparent data-[state=open]:text-mono")}
                  >
                    <GroupIcon aria-hidden="true" />
                    {t(`nav.groups.${group.key}`)}
                    {here && <span className="sr-only">: {t(`sections.${active.key}`)}</span>}
                  </NavigationMenuTrigger>
                  <NavigationMenuContent {...CLICK_ONLY} className="p-1.5 md:w-[360px]">
                    <ul className="flex flex-col gap-0.5">
                      {group.sections.map((s) => (
                        <li key={s.key}>
                          <NavigationMenuLink asChild className="flex-row gap-3 p-2.5">
                            <SectionRow section={s} active={s.key === active.key} />
                          </NavigationMenuLink>
                        </li>
                      ))}
                    </ul>
                  </NavigationMenuContent>
                </NavigationMenuItem>
              );
            })}
          </NavigationMenuList>
        </NavigationMenu>

        <div className="flex items-center gap-5">
          {UTILITY_SECTIONS.map((s) => {
            const Icon = s.icon;
            const here = s.key === active.key;
            return (
              <Link key={s.key} href={s.href} data-here={here || undefined} aria-current={here ? "page" : undefined} className={BAR_ITEM}>
                <Icon aria-hidden="true" />
                {t(`sections.${s.key}`)}
                {s.key === "alerts" && unread > 0 && (
                  <Badge variant="primary" size="sm" className="ms-0.5" aria-label={t("nav.unread", { n: unread })}>
                    {unread > 99 ? "99+" : unread}
                  </Badge>
                )}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

