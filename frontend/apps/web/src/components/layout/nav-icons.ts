/** Icons for main menu entries, kept on the client side because icons cannot be passed from
 * server components as props. */
import {
  BadgeCheck,
  Briefcase,
  Building2,
  Compass,
  House,
  type LucideIcon,
  Newspaper,
  Percent,
  ShieldUser,
  Wallet,
  Zap,
} from "lucide-react";

import type { NavKey } from "@/lib/nav";

export const NAV_ICONS: Partial<Record<NavKey, LucideIcon>> = {
  home: House,
  companies: Building2,
  shariah: BadgeCheck,
  rates: Percent,
  events: Zap,
  macro: Newspaper,
  regime: Compass,
  personal: Wallet,
  firm: Briefcase,
  admin: ShieldUser,
};
