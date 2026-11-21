# Frontend

npm workspaces. Root rules in [../CLAUDE.md](../CLAUDE.md) apply here; commands are listed there.

| Path | Holds |
|-|-|
| `apps/web/` | Next.js web app (App Router, server components, Tailwind CSS 4, next-intl) |
| `packages/core/` | Formatting (taka, lakh and crore, Bangla digits, Dhaka dates) and API types. No React, no Next.js: the mobile app will import it. |
| `packages/i18n/` | `messages/bn.json`, `messages/en.json`, locale list. Shared with the mobile app. |
| `apps/mobile/` | Not created yet. Expo app, planned after the web releases (F11). |

## Rules

- **No calculations in the client.** Zakat, screening, returns and FIRE numbers come from the API. The client formats and displays.
- **Every user-facing string is a message key** in both `bn.json` and `en.json`. A test fails if the two files differ in keys or placeholders. English is the reference for types.
- **Format numbers, money and dates with `@analysisace/core`** (`formatBDT`, `formatNumber`, `formatPercent`, `formatDate`). Do not call `toLocaleString` or `Intl` in components. Pass money as the decimal string from the API; never `parseFloat` it.
- **Digits** follow the language for now (`digitsFor` in `apps/web/src/lib/locale.ts`). They become a user setting when accounts exist.
- **Analytical pages show `<Disclaimer />`** and API data blocks show `<DataFootnote />` (as-of time and sources).
- **Links use `Link` from `@/i18n/navigation`**, not `next/link`, so the locale prefix is kept.
- **Fetch data in server components** through `apps/web/src/lib/api.ts`. The browser never calls the API and never sees the session token.
- **Mobile first.** Check every page at 360 px width. WCAG 2.1 AA: labels on inputs, visible focus, sufficient contrast in light and dark.
- **Brand:** use `<Logo />` from `components/brand/logo.tsx`, never an image file. Colours are navy, teal and deep teal (docs/DECISIONS.md, D14). Regenerate icons with `npm run brand:assets`.
- **Colours come from the Metronic tokens** in `apps/web/src/app/globals.css` (`bg-background`, `bg-card`, `text-mono` for headings, `text-secondary-foreground` for body, `text-muted-foreground` for hints, `bg-primary`, `border-border`). Do not hard-code hex values in components.
- Mark text that stays in Latin script inside Bangla pages (tickers, company names) with `lang="en"`.

## Design: Metronic 9, Layout 9

- Build pages from the components in `apps/web/src/components/ui` (copied from the licensed Metronic starter kit) and the shell in `components/layout`. Start each page with `<Toolbar title breadcrumbs>` and put content in a `container` div, usually inside `Card`s.
- Need a Metronic component that is not here yet? Copy that one file from the theme's `metronic-tailwind-react-starter-kit/typescript/nextjs/components/ui`, plus anything it imports. Do not copy whole folders, demo pages or sample data. The theme download lives outside the repo.
- Files in `components/ui` are vendor code: change them only to fix a real defect, and keep app-specific styling in the calling component.
- Copied so far beyond the first set: `navigation-menu`, `tabs`, `toggle`, `toggle-group`, `tooltip`. A server component cannot call helpers from these client files (such as `toggleVariants`); repeat the classes instead, as `components/market/segmented-links.tsx` does.
- Metronic layouts are client components with fixed English text. Ours are adapted: text comes from messages, links use our locale-aware `Link`, and only the parts that need the browser are client components.
- Dark mode follows the `.dark` class set by `next-themes`. Check new pages in both themes.

## Accounts in the web app

- `src/lib/session.ts`: `getCurrentUser()`, `requireUser(locale, returnTo)`, `requirePermission(locale, returnTo, permission)`. Call a guard at the top of every protected page.
- Forms post to server actions in `src/app/actions/` and use `useActionState` with `Field`, `SubmitButton` and `FormMessage` from `components/form/form-parts.tsx`. Actions return an error code; `FormMessage` translates it from the `errors` messages.
- Hiding a menu item is for convenience only. The API enforces every permission.
- Menu entries are defined in `src/lib/nav.ts`. Market pages sit under the "Markets" group (a Layout 9 dropdown); their icons are in `components/layout/nav-icons.ts`, because icons cannot be passed from server components.
- Dropdown menus open on click only (`CLICK_ONLY` in the navbars): with hover opening too, pointing at a group and clicking it closes it again.

## Personal finance pages ("My money", F12 to F26)

- Pages live under `app/[locale]/(site)/personal/`. The paths match the links the API stores in notifications (`/personal/allocation`, `/personal/assets/{id}` and so on), so do not rename them.
- Sections are grouped by task in `src/lib/personal-sections.ts` (Overview, Costs, What you own, How it's doing, Zakat and tax, Plans; Alerts and Household apart). The section menu, the phone sheet and the overview's "All sections" panel all read it, so a new page is added there once, with an icon and a `personal.nav.describe.<key>` line in both message files.
- Start a page with `setup(locale, returnTo)` from `src/lib/personal-page.ts` and wrap it in `<PersonalShell>`, which adds the toolbar, the household switcher, the "create a household" card and the disclaimer.
- Read API data with `hh(ctx, path)` (household routes) or `get(ctx, path)`, wrapped in `load(...)` so one failing block shows an error in place instead of breaking the page.
- Writes go through `src/app/actions/personal.ts`. Pass them bound (`action.bind(null, householdId, ...)`) to `ActionForm`, `DeleteButton`, `ActionButton` or `ToggleSwitch` from `components/personal/forms.tsx`.
- Label API values with `enumLabel(t, group, value)`; the labels live under `personal.enum.<group>` in both message files.
- Format with `formatterFor(locale)` from `src/lib/fmt.ts` (`f.bdt`, `f.compact`, `f.pct`, `f.date`). Charts use `components/personal/line-chart.tsx` with the `--viz-1..4` colour tokens.
- Files (CSV exports, documents) download through `/personal/download?path=...`; add a new file route to its allow-list.

## Next.js 16 notes

- `params` and `searchParams` are promises: `await` them (or `use()` in non-async components).
- Request interception lives in `src/proxy.ts` (the file was called `middleware.ts` before Next.js 16).
- Call `setRequestLocale(locale)` at the top of each page and layout so static rendering works.

## Tooling notes

- TypeScript is pinned to 6.0.x because `typescript-eslint` does not support 6.1 or 7 yet.
- `npm test` runs Vitest through `scripts/run-vitest.mjs`. On Windows, Vitest fails when the working directory has a lower-case drive letter (`d:\`); the script corrects it. Do not call `vitest` directly.
- Browser tests live in `e2e/` (Playwright, desktop and 360 px). They need the full stack running. Next.js adds its own empty `role="alert"` element, so select messages by text, not by `getByRole("alert")`.
- Adding a page: add its message keys in both languages first, then the page under `apps/web/src/app/[locale]/`.
