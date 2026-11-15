"use client";

import type { User } from "@analysisace/core";
import { Menu, Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetBody, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useScrollPosition } from "@/hooks/use-scroll-position";
import { Link, usePathname } from "@/i18n/navigation";
import { isActivePath, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { LocaleSwitcher } from "./locale-switcher";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";

interface Props {
  user: User | null;
  items: NavItem[];
}

/** Metronic Layout 9 header: logo, search and account controls in a fixed top bar. */
export function SiteHeader({ user, items }: Props) {
  const t = useTranslations();
  const sticky = useScrollPosition() > 0;

  return (
    <header
      className={cn(
        "fixed start-0 end-0 top-0 z-10 flex h-(--header-height) shrink-0 items-center bg-background/70 transition-all duration-300",
        sticky && "shadow-xs backdrop-blur-md",
      )}
    >
      <div className="container flex items-center justify-between gap-2.5">
        <div className="flex items-center gap-1 lg:w-[320px]">
          <MobileMenu items={items} />
          <Link href="/" className="shrink-0">
            <Logo wordmark="sm" />
          </Link>
        </div>

        <SearchForm className="hidden md:block" />

        <div className="flex items-center justify-end gap-2 lg:w-[320px]">
          <LocaleSwitcher />
          <ThemeToggle />
          {user ? (
            <UserMenu user={user} />
          ) : (
            <>
              <Button variant="outline" asChild>
                <Link href="/signin">{t("nav.signIn")}</Link>
              </Button>
              {/* On phones only "Sign in" fits; the sign-in page links to sign-up. */}
              <Button variant="mono" asChild className="hidden sm:inline-flex">
                <Link href="/signup">{t("nav.signUp")}</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

/** Company search. A plain GET form, so it works before scripts load. */
function SearchForm({ className, id = "header-search" }: { className?: string; id?: string }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  return (
    <form action={`/${locale}/companies`} role="search" className={className}>
      <label htmlFor={id} className="sr-only">
        {t("searchPlaceholder")}
      </label>
      <div className="relative">
        <Search className="absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id={id}
          type="search"
          name="q"
          maxLength={50}
          placeholder={t("searchPlaceholder")}
          className="min-w-0 ps-9 md:w-64"
        />
      </div>
    </form>
  );
}

/** Below the `lg` breakpoint the menu bar is replaced by this slide-in menu. */
function MobileMenu({ items }: { items: NavItem[] }) {
  const t = useTranslations();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="lg:hidden">
      <Button variant="dim" mode="icon" aria-label={t("common.openMenu")} onClick={() => setOpen(true)}>
        <Menu />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-[275px] gap-0 p-0">
          <SheetHeader className="border-b border-border p-4">
            <SheetTitle>{t("nav.label")}</SheetTitle>
          </SheetHeader>
          <SheetBody className="space-y-4 overflow-y-auto p-4">
            <SearchForm id="menu-search" />
            <nav aria-label={t("nav.label")} className="flex flex-col gap-1">
              {items.map((item) => (
                <Link
                  key={item.key}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActivePath(pathname, item.href) ? "page" : undefined}
                  className="rounded-md px-3 py-2.5 text-sm font-medium text-secondary-foreground hover:bg-accent aria-[current=page]:bg-accent aria-[current=page]:text-mono"
                >
                  {t(`nav.${item.key}`)}
                </Link>
              ))}
            </nav>
          </SheetBody>
        </SheetContent>
      </Sheet>
    </div>
  );
}
