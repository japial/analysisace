import type { User } from "@analysisace/core";

export interface NavItem {
  /** Message key under `nav`. */
  key: "home" | "companies" | "adminUsers" | "adminRoles";
  href: string;
}

/** Main menu for a visitor. Admin entries appear only for people who may use them. */
export function navItems(user: User | null): NavItem[] {
  const items: NavItem[] = [
    { key: "home", href: "/" },
    { key: "companies", href: "/companies" },
  ];
  if (user?.permissions.includes("USERS_MANAGE")) {
    items.push({ key: "adminUsers", href: "/admin/users" });
    items.push({ key: "adminRoles", href: "/admin/roles" });
  }
  return items;
}

/** True when `pathname` (without locale prefix) is `href` or a page under it. */
export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
