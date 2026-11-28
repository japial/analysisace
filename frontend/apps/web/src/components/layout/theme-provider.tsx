"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/**
 * next-themes renders an inline script that sets light or dark before the first paint.
 * React 19 warns about any <script> rendered by a component. The script only has to run
 * from the server HTML, so in the browser it is marked as data and React stays quiet.
 * The attribute difference is covered by the script's own suppressHydrationWarning.
 */
const scriptProps =
  typeof window === "undefined" ? undefined : ({ type: "application/json" } as const);

export function ThemeProvider(props: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider scriptProps={scriptProps} {...props} />;
}
