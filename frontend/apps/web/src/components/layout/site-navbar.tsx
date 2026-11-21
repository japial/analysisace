"use client";

import { useTranslations } from "next-intl";

import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu";
import { Link, usePathname } from "@/i18n/navigation";
import { type NavItem, isActiveItem, isActivePath } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { NAV_ICONS } from "./nav-icons";

/** Undo the menu link's own panel styling for links that sit in the bar itself. */
const LINK_RESET = "flex-row gap-0 rounded-none p-0 hover:bg-transparent focus:bg-transparent focus-visible:ring-0";

/**
 * Open the dropdowns on click (or Enter) only. With hover opening as well, a person who
 * points at a group and then clicks it closes it again, and touch screens have no hover.
 */
const CLICK_ONLY = {
  onPointerMove: (event: { preventDefault: () => void }) => event.preventDefault(),
  onPointerLeave: (event: { preventDefault: () => void }) => event.preventDefault(),
};

const BAR_LINK =
  "-mb-px inline-flex h-12 items-center border-b border-transparent text-sm font-medium text-secondary-foreground hover:text-mono focus-visible:text-mono data-[here=true]:border-mono data-[here=true]:text-mono";

/**
 * Metronic Layout 9 menu bar under the header. Shown from the `lg` breakpoint up.
 * A group (Markets) opens a panel listing its pages with an icon and one line each.
 */
export function SiteNavbar({ items }: { items: NavItem[] }) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <div className="hidden border-y border-border bg-muted/80 lg:block">
      <div className="container">
        <NavigationMenu viewport={false} aria-label={t("label")}>
          <NavigationMenuList className="gap-6">
            {items.map((item) => {
              const here = isActiveItem(pathname, item);
              if (!item.children) {
                return (
                  <NavigationMenuItem key={item.key}>
                    <NavigationMenuLink asChild className={cn(LINK_RESET, BAR_LINK)}>
                      <Link href={item.href} data-here={here || undefined} aria-current={here ? "page" : undefined}>
                        {t(item.key)}
                      </Link>
                    </NavigationMenuLink>
                  </NavigationMenuItem>
                );
              }
              return (
                <NavigationMenuItem key={item.key}>
                  <NavigationMenuTrigger
                    {...CLICK_ONLY}
                    data-here={here || undefined}
                    className={cn(BAR_LINK, "h-12 gap-1 rounded-none bg-transparent! px-0 py-0 hover:bg-transparent data-[state=open]:text-mono")}
                  >
                    {t(item.key)}
                  </NavigationMenuTrigger>
                  <NavigationMenuContent {...CLICK_ONLY} className="p-0 md:w-[420px]">
                    <p className="border-b border-border bg-accent/30 px-4 py-3 text-xs text-secondary-foreground">
                      {t("marketsIntro")}
                    </p>
                    <ul className="flex flex-col gap-0.5 p-1.5">
                      {item.children.map((child) => {
                        const Icon = NAV_ICONS[child.key];
                        const current = isActivePath(pathname, child.href);
                        return (
                          <li key={child.key}>
                            <NavigationMenuLink
                              asChild
                              className="group/row flex-row items-start gap-3 rounded-lg p-2.5 hover:bg-accent/60 focus:bg-accent/60 aria-[current=page]:bg-primary/5"
                            >
                              <Link href={child.href} aria-current={current ? "page" : undefined}>
                                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground group-hover/row:text-primary group-aria-[current=page]/row:text-primary">
                                  {Icon && <Icon className="size-4" aria-hidden="true" />}
                                </span>
                                <span className="flex flex-col">
                                  <span className="text-sm font-medium text-mono">{t(child.key)}</span>
                                  <span className="text-xs text-muted-foreground">
                                    {t(`describe.${child.key}` as "describe.shariah")}
                                  </span>
                                </span>
                              </Link>
                            </NavigationMenuLink>
                          </li>
                        );
                      })}
                    </ul>
                  </NavigationMenuContent>
                </NavigationMenuItem>
              );
            })}
          </NavigationMenuList>
        </NavigationMenu>
      </div>
    </div>
  );
}
