import type { Permission, User } from "@analysisace/core";

export type NavKey =
  | "home"
  | "companies"
  | "markets"
  | "shariah"
  | "rates"
  | "events"
  | "macro"
  | "regime"
  | "personal"
  | "admin";

export interface NavItem {
  /** Message key under `nav`. */
  key: NavKey;
  href: string;
  /** A group shown as a dropdown (desktop) or a labelled list (phone menu). */
  children?: NavItem[];
}

/** Permissions that open at least one screen of the admin area. */
export const ADMIN_PERMISSIONS: readonly Permission[] = [
  "USERS_MANAGE",
  "DATA_REVIEW",
  "CONTENT_PUBLISH",
  "SHARIAH_OVERRIDE",
  "CONFIG_MANAGE",
  "AUDIT_VIEW",
];

/** The market pages (F1 to F8), grouped under "Markets" so the menu bar stays short. */
export const MARKET_ITEMS: NavItem[] = [
  { key: "shariah", href: "/shariah" },
  { key: "rates", href: "/rates" },
  { key: "events", href: "/events" },
  { key: "macro", href: "/macro" },
  { key: "regime", href: "/regime" },
];

/** Main menu for a visitor. The admin entry appears only for people who may use it. */
export function navItems(user: User | null): NavItem[] {
  const items: NavItem[] = [
    { key: "home", href: "/" },
    { key: "companies", href: "/companies" },
    { key: "markets", href: "/shariah", children: MARKET_ITEMS },
  ];
  // Personal finance (F12 to F26) belongs to a signed-in person.
  if (user) items.push({ key: "personal", href: "/personal" });
  if (user?.permissions.some((p) => ADMIN_PERMISSIONS.includes(p))) {
    items.push({ key: "admin", href: "/admin" });
  }
  return items;
}

/** True when `pathname` (without locale prefix) is `href` or a page under it. */
export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** True when the item or one of its children is the current page. */
export function isActiveItem(pathname: string, item: NavItem): boolean {
  if (item.children) return item.children.some((child) => isActivePath(pathname, child.href));
  return isActivePath(pathname, item.href);
}
