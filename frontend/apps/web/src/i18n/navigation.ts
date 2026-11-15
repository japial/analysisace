import { createNavigation } from "next-intl/navigation";

import { routing } from "./routing";

// Locale-aware versions of Link, redirect and the router hooks. Use these, not next/link.
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
