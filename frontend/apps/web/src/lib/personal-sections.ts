/**
 * How the "My money" sections are grouped. Fifteen pages are too many for one row of tabs,
 * so they are grouped by the task a person has in mind (card-sorting groups):
 * everyday spending, what the household owns, how it is doing, religious and legal duties,
 * and plans. Alerts and the household settings sit apart, as utilities.
 *
 * Used by the section menu (desktop dropdowns, phone sheet) and the overview's shortcuts.
 */
import {
  Bell,
  ChartColumn,
  ChartPie,
  FileText,
  Flag,
  Flame,
  HandCoins,
  HandHeart,
  House,
  Landmark,
  LayoutDashboard,
  type LucideIcon,
  Receipt,
  Scale,
  ShieldCheck,
  Target,
  TrendingUp,
  Users,
  UsersRound,
  Wallet,
} from "lucide-react";

export type SectionKey =
  | "overview"
  | "costs"
  | "portfolio"
  | "assets"
  | "sukuk"
  | "performance"
  | "allocation"
  | "marketCheck"
  | "zakat"
  | "tax"
  | "fire"
  | "goals"
  | "community"
  | "alerts"
  | "household";

export interface Section {
  key: SectionKey;
  href: string;
  icon: LucideIcon;
}

export interface SectionGroup {
  /** Message key under `personal.nav.groups`. */
  key: "overview" | "costs" | "wealth" | "insights" | "duties" | "plans";
  icon: LucideIcon;
  sections: Section[];
}

export const SECTION_GROUPS: SectionGroup[] = [
  { key: "overview", icon: LayoutDashboard, sections: [{ key: "overview", href: "/personal", icon: LayoutDashboard }] },
  { key: "costs", icon: Receipt, sections: [{ key: "costs", href: "/personal/costs", icon: Receipt }] },
  {
    key: "wealth",
    icon: Wallet,
    sections: [
      { key: "portfolio", href: "/personal/portfolio", icon: Landmark },
      { key: "assets", href: "/personal/assets", icon: House },
      { key: "sukuk", href: "/personal/sukuk", icon: HandCoins },
    ],
  },
  {
    key: "insights",
    icon: ChartColumn,
    sections: [
      { key: "performance", href: "/personal/performance", icon: TrendingUp },
      { key: "allocation", href: "/personal/allocation", icon: ChartPie },
      { key: "marketCheck", href: "/personal/market-check", icon: ShieldCheck },
    ],
  },
  {
    key: "duties",
    icon: Scale,
    sections: [
      { key: "zakat", href: "/personal/zakat", icon: HandHeart },
      { key: "tax", href: "/personal/tax", icon: FileText },
    ],
  },
  {
    key: "plans",
    icon: Target,
    sections: [
      { key: "fire", href: "/personal/fire", icon: Flame },
      { key: "goals", href: "/personal/goals", icon: Flag },
      { key: "community", href: "/personal/community", icon: Users },
    ],
  },
];

/** Shown on the right of the menu bar, and last in the phone sheet. */
export const UTILITY_SECTIONS: Section[] = [
  { key: "alerts", href: "/personal/alerts", icon: Bell },
  { key: "household", href: "/personal/household", icon: UsersRound },
];

export const ALL_SECTIONS: Section[] = [...SECTION_GROUPS.flatMap((g) => g.sections), ...UTILITY_SECTIONS];

/** The section a path belongs to; detail pages (a holding, a Zakat snapshot) map to their parent. */
export function currentSection(pathname: string): Section {
  const match = ALL_SECTIONS.filter((s) => s.href !== "/personal" && (pathname === s.href || pathname.startsWith(`${s.href}/`)));
  return match.sort((a, b) => b.href.length - a.href.length)[0] ?? ALL_SECTIONS[0]!;
}
