"use client";

import type { User } from "@analysisace/core";
import { LogOut, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";

import { signOutAction } from "@/app/actions/auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link } from "@/i18n/navigation";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts;
  return letters.map((part) => Array.from(part ?? "")[0] ?? "").join("").toUpperCase() || "?";
}

export function UserMenu({ user }: { user: User }) {
  const t = useTranslations();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="cursor-pointer rounded-full">
        {/* Named by hidden text, not aria-label: the initials are decoration (WCAG 2.5.3). */}
        <span className="sr-only">{t("nav.userMenu")}</span>
        <Avatar className="size-9" aria-hidden="true">
          <AvatarFallback className="bg-primary text-sm font-medium text-primary-foreground">
            {initials(user.full_name)}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="flex flex-col gap-0.5">
          <span className="truncate text-sm font-medium text-mono">{user.full_name}</span>
          <span className="truncate text-xs font-normal text-muted-foreground" lang="en">
            {user.email}
          </span>
          <span className="text-xs font-normal text-muted-foreground">
            {t(`roles.${user.role}.name`)}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/account">
            <UserRound />
            {t("nav.account")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          {/* A form post, so signing out works without client-side routing. */}
          <form action={signOutAction}>
            <button type="submit" className="flex w-full cursor-pointer items-center gap-2">
              <LogOut className="size-4" />
              {t("nav.signOut")}
            </button>
          </form>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
