# analysisACE: Product Requirements Document

|Field|Value|
|-|-|
|Product|analysisACE (analysisACE.com)|
|Document|PRD v1.0, build edition for Claude Code|
|Date|2026-11-14|
|Owner|Md. Jahangir Alom|
|Status|Approved for build, with open questions in section 17|
|Market|Bangladesh first (Dhaka Stock Exchange, taka, Bangla and English)|

\---

## 0\. Instructions for Claude Code

Read this section before writing any code.

1. **Build in milestone order** (section 14). Finish a milestone's acceptance criteria and tests before starting the next.
2. **Reference requirement IDs** (for example `FR1.2`) in commit messages, test names and code comments where a function implements a requirement.
3. **Configuration over constants.** Every Shariah threshold, Zakat rule, nisab weight, benchmark, schedule and excluded date range lives in versioned config (`config/\*.yaml` or a `settings` table), never hard-coded. Several values in this PRD are approximate and will change after review by a Shariah advisor.
4. **Hard rules (never break):**

   * No buy, sell or hold recommendations, target prices or trading signals anywhere in the UI, API, emails or reports. Use descriptive language ("historically moved", "drift from your target").
   * Never store or display the DSE's licensed DSES constituent list. analysisACE runs its own screening.
   * No crypto exchange or wallet integrations (crypto trading is illegal in Bangladesh per Bangladesh Bank).
   * Every analytical page shows the notice: "Historical analysis for education only. Not investment advice."
   * Every number shown to users must be traceable to a source record and a computation timestamp.
5. **When blocked by an open question** (section 17), implement the stated default behind a config flag and add a `TODO(owner):` comment referencing the question ID.
6. **Maintain `CLAUDE.md`** at the repo root (see Appendix A).
7. **Do not scrape a site in a way that breaks its terms of use.** Isolate each data source behind an adapter interface so a source can be swapped for a licensed feed.

\---

## 1\. Product overview

analysisACE is a personal finance web app for Bangladeshi households. Its purpose is to help a household grow its **ACE**:

* **Assets:** what the household owns and owes (accounts, savings certificates, gold, land, business stakes, debts), with Zakat and the wealth statement worked out from them.
* **Capital:** the part of those assets put to work (DSE shares, sukuk, Islamic deposits, alternative investments), its returns and mix, and the plans it funds (FIRE, goals).
* **Earnings:** income, costs, tax deducted and monthly savings, which feed Capital and the plans.

The goal the product is organised around is **financial independence (FIRE)**: the point at which a household's invested capital could cover its yearly costs. Assets, Capital and Earnings are the three levers that move a household's FIRE date, and the savings rate (Earnings) is presented as the biggest of them.

DSE stocks are one kind of capital. The market tools (Shariah screen, rate sensitivity, shock playbook, macro notes, regime) are an optional layer for households that hold shares. They are not the product's centre and must not lead the landing page, the menu or the roadmap.

**Problem**

* Bangladeshi households track bank accounts, savings certificates, FDRs, DPS, sukuk, gold, land and shares in separate places, and calculate Zakat by hand.
* Few people can say what the household is worth today, what share of it is working for them, or how much they really save each month.
* Shariah-minded households that do own shares cannot check compliance cheaply: the DSE sells its Shariah index (DSES) constituent list as paid data (Tk 5 lakh once plus Tk 1.2 lakh a year). No DSE tool links stock behaviour to treasury bill yields or past crises (the DSEX fell 4.42% on 8 March 2026 in the Iran war shock).

**Positioning**

* **One picture of the household's money:** assets, capital and earnings together, so each change shows its effect on the others.
* **Built for Bangladesh:** taka, Bangla, local asset types (sanchayapatra, DPS, Mudaraba deposits), Zakat, the July-to-June tax year.
* **Transparent and traceable:** every number shows its source and time; rules are published and versioned.
* **Stock tools with reasons:** for holders of DSE shares, a transparent Shariah screen and macro-aware analytics, as one kind of capital.

\---

## 2\. Goals, non-goals, success metrics

### Goals

* G1. Give households one place to see their ACE: assets and net worth, capital at work, and earnings, costs and savings.
* G2. Make Zakat, the wealth statement and FIRE and goal progress follow from those records with no extra work.
* G3. Publish a free, transparent Shariah screen for every DSE-listed company, as a tool for households that hold shares.
* G4. Quantify each stock's sensitivity to T-bill yields and its behaviour in past shocks, as a tool for the same households.
* G5. Reach paying individual and firm customers within nine months of build start.

### Non-goals

* Investment advice, recommendations or signals.
* Trading, order routing, or holding customer money.
* Mutual fund holdings tables (ReturnKoto covers this).
* Real-time intraday data in year one (end-of-day only).
* Automatic broker or bank account connections in year one (manual entry and file upload only).
* Crypto integrations.

### Success metrics (targets to confirm after user interviews)

|Metric|Target|When|
|-|-|-|
|Households with at least one asset, one cost record and one income record|300|6 months after launch|
|Weekly returning users|1,000|3 months after launch|
|DSE equities screened with reasons shown|100% of listed equities|Stock tools launch|
|Paying individual subscribers|100|Month 9|
|Firm pilots (broker, asset manager, Islamic bank)|3|Month 9|
|Price data freshness|By 18:00 Asia/Dhaka on trading days|Ongoing|
|Yield data freshness|Within 1 day of each auction|Ongoing|

\---

## 3\. Users

|Persona|Description|Main job|Plan|
|-|-|-|-|
|Household planner (primary)|Salaried or business-owning family, mobile-first, often prefers Bangla|See net worth, savings and Zakat in one place; plan FIRE and goals|Free, then Pro|
|Shariah-minded saver|Keeps money in sukuk, Islamic deposits, gold and shares|Calculate Zakat; check which holdings are halal and why|Free, then Pro|
|Share-holding investor|Holds DSE stocks as part of the portfolio|Understand how rates and shocks affect the shares held|Pro|
|Broker research desk|Brokerage research team|Ready-made weekly client content|Firm|
|Shariah fund manager|Asset manager with a Shariah fund|Compliance and macro exposure of holdings|Firm|
|Islamic bank wealth desk|Advisers for Islamic banking clients|Explainable Shariah list for clients|Firm|

### Core user stories

* US1. As a Shariah investor, I search a stock and see pass or fail, each rule tested, the company's figures and their source report.
* US2. As a holder, I am notified when a stock I hold changes Shariah status.
* US3. As an active investor, I see how my stock historically moved per 1-point change in the T-bill yield.
* US4. When a shock starts, I see how my stocks behaved in similar past events and how long they took to recover.
* US5. I log daily costs and see my monthly and yearly cost of living.
* US6. I record all my assets once and get a Zakat calculation and the figures for my tax return.
* US7. I see my combined net worth across shares, sukuk, Islamic bank deposits, gold and land.
* US8. I enter savings and expenses and see when I can reach FIRE, and how a 20% crash changes that.
* US9. My spouse and I share a household view while Zakat and tax stay per person.
* US10. As a broker researcher, I download a white-label weekly report and export data by CSV or API.

\---

## 4\. Feature map

|ID|Feature|Layer|Release|Priority|Plan|
|-|-|-|-|-|-|
|F1|Shariah screen per company|Market|MVP|Must|Free|
|F2|Shariah list and DSES vs DSEX tracker|Market|MVP|Must|Free|
|F3|Rate sensitivity score|Market|MVP|Must|Free summary, Pro detail|
|F4|Weekly macro note (bn, en)|Market|MVP|Should|Free|
|F5|Shock playbook|Market|R2|Must|Free events, Pro per-stock|
|F6|Portfolio check (Shariah share, rate and shock exposure, purification)|Market|R2|Must|Pro|
|F7|Alerts (status, regime, shock)|Market|R2|Should|Pro|
|F8|Macro regime dashboard|Market|R3|Should|Pro|
|F9|Firm features (white-label, CSV, API, seats)|Market|R3|Should|Firm|
|F10|Ownership change layer|Market|Later|Could|Pro|
|F11|Native mobile app|Platform|Later|Could|n/a|
|F12|Daily cost records|Personal|R2|Must|Free|
|F13|Tax and Zakat snapshot|Personal|R2|Must|Free basic, Pro full|
|F14|Portfolio aggregation|Personal|R2|Must|Free basic, Pro full|
|F15|Performance tracking|Personal|R3|Should|Pro|
|F16|Asset allocation and drift|Personal|R3|Should|Pro|
|F17|FIRE calculator|Personal|R3|Must|Free basic, Pro full|
|F18|Scenario planning|Personal|R3+|Should|Pro|
|F19|Goal tracking|Personal|R3|Should|Free|
|F20|Alerts and monthly report (personal)|Personal|R3|Should|Pro|
|F21|Community benchmarking|Personal|Later|Could|Free|
|F22|News sentiment (information only)|Market|Later|Could|Pro|
|F23|Data privacy controls|Platform|Every release|Must|All|
|F24|Multi-owner household records|Personal|R3+|Should|Pro|
|F25|Alternative investments|Personal|R2 (basic), R3 (cash flows, XIRR, documents)|Must|Pro|
|F26|Sukuk and Islamic bank investments|Personal|R2 (holdings, calendar), R3 (comparison, safety panel)|Must|Free basic, Pro full|
|F27|Income records and savings|Personal|R2|Must|Free|

R2 ships before Ramadan 2027 (around early February 2027), when most users calculate Zakat.

### ACE map

Every feature belongs to a pillar. "Layer" above is a technical grouping; the pillar is how the product, menu and marketing are organised.

|Pillar|Features|
|-|-|
|**Assets**|F14 portfolio aggregation (the asset register), F25 alternative investments, F26 sukuk and Islamic bank holdings, F24 multi-owner household, F13 Zakat and wealth statement|
|**Capital**|F15 performance, F16 allocation and drift, F17 FIRE, F18 scenarios, F19 goals, F6 portfolio check, and the stock tools F1 to F5, F8, F10, F22|
|**Earnings**|F12 daily costs, F27 income records and savings rate, tax deducted (F13), F20 alerts and monthly report|
|Platform|F7 alerts, F9 firm features, F11 mobile app, F21 community benchmarking, F23 privacy|

Build priority follows the pillars: Assets and Earnings first (nothing waits on a data licence), then Capital plans, then the stock tools as data licensing (Q5) allows.

\---

## 5\. Functional requirements: market intelligence

Each requirement has acceptance criteria (AC) that tests must cover.

### F1 Shariah screen per company

* FR1.1 Each company has a status: `COMPLIANT`, `NON\_COMPLIANT`, `UNDER\_REVIEW`.
* FR1.2 Show every rule tested: rule name, company value, threshold, pass or fail.
* FR1.3 Each financial figure links to its source document (report URL, period, page if known).
* FR1.4 Re-screen within 7 days of new quarterly or annual financials; keep full status history.
* FR1.5 Show "last screened" date and methodology version.
* FR1.6 Admin can add a Shariah board note and a manual override with a mandatory reason; overrides are audited.
* AC: given a seeded company with known figures, the screen produces the expected status and per-rule results for both methodologies in section 7; any missing input yields `UNDER\_REVIEW`; a ratio within the configured margin of its threshold yields `UNDER\_REVIEW`.

### F2 Shariah list and index tracker

* FR2.1 Filterable, sortable list of screened companies (status, sector, market cap, last screened).
* FR2.2 Chart comparing an equal-weight analysisACE Shariah basket with DSES and DSEX over 1, 3, 5 years (rebased to 100).
* FR2.3 The DSE DSES constituent list is never stored or shown (index level only).
* AC: basket rebalances monthly from current `COMPLIANT` set; chart values reproducible from stored prices.

### F3 Rate sensitivity score

* FR3.1 For each stock and sector, estimate weekly OLS:
`r\_i,t = a + b \* Δy\_t + c \* r\_DSEX,t + e\_t`, where `r` = weekly log return of adjusted close and `Δy` = weekly change in 91-day T-bill cut-off yield (percentage points). Report `b × 1` as "% move per 1-point yield rise". Also compute a version without the market term.
* FR3.2 Sample: up to 5 years of weekly data; exclude configured floor-price periods and weeks with no trading; minimum 104 valid weeks, else "insufficient data".
* FR3.3 Confidence: `HIGH` if |t| ≥ 2.5 (Newey-West SE), `MEDIUM` if 1.5 ≤ |t| < 2.5, else `LOW`. Show sample period and N.
* FR3.4 Recompute after each T-bill auction is ingested.
* FR3.5 Show the latest auction results and 12-month yield trend beside the score.
* AC: unit tests on synthetic data recover a known `b` within tolerance; excluded periods are not used.

### F4 Weekly macro note

* FR4.1 Auto-generated weekly page (draft, then admin publish): yields, policy rate, CPI inflation, BDT/USD, remittance, Brent, DSEX and DSES weekly change, and a "what changed" list.
* FR4.2 Bangla and English versions; admin can edit text before publish.
* AC: draft generates from stored data only; no figure without a source link.

### F5 Shock playbook

* FR5.1 Event library: id, type (`WAR`, `ENERGY`, `POLITICAL`, `POLICY`, `OTHER`), start date (`t0`), title, description, source links. Admin-curated.
* FR5.2 For each event × stock and sector: returns at +1, +5, +20 sessions vs close of the last session before `t0`; max drawdown within 60 sessions; sessions to recover to the pre-event close (or "not recovered").
* FR5.3 "Similar events" for a new event: same type, ranked by recency; show their outcomes for the user's holdings.
* Seed events: Russia-Ukraine (2022-02-24), US strikes in the Iran-Israel war (2025-06-22), strikes on Iran (2026-02-28), Maheshkhali LNG terminal fire (late July 2026, exact date to curate), plus policy-rate changes from Bangladesh Bank.
* AC: event metrics reproducible from stored prices; corporate-action-adjusted prices used.

### F6 Portfolio check (market layer)

* FR6.1 Uses F14 holdings (DSE shares and listed mutual funds).
* FR6.2 Show Shariah share of portfolio value, value-weighted rate sensitivity, and historical shock exposure (weighted average of F5 metrics).
* FR6.3 Dividend purification estimate where non-permissible income ratio is known: `dividend × non\_permissible\_income\_ratio`.
* AC: weights sum to 100%; unknown-status holdings shown separately.

### F7 Alerts

* FR7.1 Email and web push when a held or watched stock changes Shariah status.
* FR7.2 Alerts when the regime label changes (F8) or a new shock event is published.
* FR7.3 User-level preferences: channel, frequency (instant, daily digest).

### F8 Macro regime dashboard

* FR8.1 Monthly rules-based regime from config: rate trend (3-month change in 91-day yield: easing if ≤ −0.5 pt, tightening if ≥ +0.5 pt, else flat), inflation band, liquidity trend, oil shock flag (Brent 1-month change ≥ +15%). Label example: "Easing, inflation high, oil calm".
* FR8.2 For the current regime: each sector's historical average monthly return and hit rate in past months with the same label.

### F9 Firm features

* FR9.1 White-label weekly PDF (firm logo, name, disclaimer).
* FR9.2 CSV export and read-only REST API with per-firm keys, rate limits, usage logs.
* FR9.3 Firm accounts with seats and roles (`ADMIN`, `MEMBER`).

### F10 Ownership change layer (later)

* Monthly sponsor/director, government, institute, foreign and public shareholding per company, and month-over-month changes.

### F22 News sentiment (later, information only)

* Bangla and English news sentiment per stock with article links. Never phrased as a signal.

\---

## 6\. Functional requirements: personal finance

### F12 Daily cost records

* FR12.1 Fast mobile entry: amount (BDT), category, date, note. Default categories in Bangla and English: food and bazar, rent, transport, utilities, education, health, family support, religious giving, other. User-defined categories allowed.
* FR12.2 Recurring entries (monthly rent, DPS instalment, school fees).
* FR12.3 Monthly and yearly totals, category trends, and inflation-adjusted view using BBS CPI.
* FR12.4 Trailing-12-month cost of living feeds F17.
* FR12.5 CSV import and export.
* AC: totals match sum of entries; recurring entries generate on schedule without duplicates.

### F27 Income records and savings

* FR27.1 Record income: amount (BDT), kind (salary, business, rent, remittance, profit, dividend, other; the list is in `config/personal.yaml`), date, member, note.
* FR27.2 Recurring income (monthly salary, quarterly rent). Entries are written on their due dates and never twice for one rule and date.
* FR27.3 Monthly income, costs and savings (income less costs), the trailing-12-month savings rate (savings / income) and income by kind. Only months with an income or cost record are counted in averages.
* FR27.4 The average monthly savings is the starting value of the FIRE form (F17), appears on the ACE card of the My money overview, and is measured by a "saved each month" goal (F19).
* FR27.5 The tax statement (F13) takes a member's salary and other income for the tax year from the income records unless the person types them in, and says which. Kinds that would double-count income already worked out from holdings and assets (rent, profit, dividends), and exempt remittance, are listed as not counted. The mapping is in `config/personal.yaml` (`income.tax_lines`). Records for the whole household are not counted for one person.
* FR27.6 The monthly report (F20) shows last month's income and what was left after costs.
* Zakat (F13) does not read income records: Zakat is due on wealth held, and income already shows there once it sits in an account.

### F13 Tax and Zakat snapshot

* FR13.1 Snapshot on a user-chosen date of all assets and liabilities from F14, F25, F26 and manual entries.
* FR13.2 Zakat: 2.5% of net zakatable wealth if above nisab. Nisab basis user-selectable: 87.48 g gold or 612.36 g silver; price per gram entered or fetched from configured source. Bangladesh has no national nisab guideline.
* FR13.3 Shares: two methods (config): `MARKET\_VALUE` (full market value) or `ZAKATABLE\_ASSETS` (company's zakatable assets per share × shares, from F1 data). Default per open question Q2.
* FR13.4 Per-asset Zakat rules from config (section 7.3).
* FR13.5 Hawl (lunar year) date per user; reminder 30 days before.
* FR13.6 Tax view: wealth statement figures (assets and liabilities by category), income summary (salary entered by user, dividends, profit, rent, capital gains), tax deducted at source recorded on holdings, and investments eligible for rebate (config list). Export as PDF and CSV. analysisACE never files returns.
* FR13.7 Per-person calculation in multi-owner households (F24).
* AC: worked examples in tests reproduce expected Zakat for each nisab basis and share method.

### F14 Portfolio aggregation

* FR14.1 Accounts: DSE BO accounts (by broker), mutual funds, savings certificates (sanchayapatra), FDR, DPS, provident fund, cash, gold, property, foreign brokerage (CSV), other.
* FR14.2 Holdings by manual entry or upload of broker portfolio statements (CSV first; PDF parsing for top brokers later). Map tickers to `company`.
* FR14.3 Daily valuation of listed holdings from DSE prices; manual values for others.
* FR14.4 Net worth = assets − liabilities, history stored daily.
* FR14.5 No crypto connections. A generic "other asset" entry exists for users abroad.

### F15 Performance tracking

* FR15.1 Time-weighted return, money-weighted return (XIRR), volatility (annualised, weekly), max drawdown, per portfolio and account.
* FR15.2 Benchmarks: DSEX, DSES, DS30 default; S\&P 500 and NASDAQ optional for foreign holdings; 91-day T-bill as risk-free.
* FR15.3 Diversification: count of holdings, top-5 weight, sector Herfindahl index.

### F16 Asset allocation and drift

* FR16.1 Allocation by asset class, sector, single holding and Shariah status.
* FR16.2 User sets target allocation and tolerance bands; show drift and the trades that would restore the target. Never propose a target.
* FR16.3 Drift alerts when outside bands (F20).

### F17 FIRE calculator

* FR17.1 Inputs: net worth (F14), monthly savings, yearly expenses (F12, editable), expected nominal return, inflation (default BBS CPI trailing average), withdrawal rate (default 4%, editable), current age.
* FR17.2 FIRE number = yearly expenses ÷ withdrawal rate (real terms). Monthly projection with real return = (1 + nominal) ÷ (1 + inflation) − 1.
* FR17.3 Output: FIRE number, projected FIRE age, year-by-year net worth path (chart and table).
* FR17.4 Illiquid alternative assets (F25) excluded from the investable base by default; toggle to include.
* FR17.5 Default safe return can be set to the user's sukuk or deposit rate (F26).

### F18 Scenario planning

* FR18.1 Presets: market crash of X% (default 20%) in year 1, historical replay of an F5 event, expenses +Y%, retire N years earlier, inflation shock.
* FR18.2 Output: change in FIRE age and worst-year net worth vs base case.

### F19 Goal tracking

* FR19.1 Goals by amount (net worth, invested amount), date, or FIRE age; progress bars; notification when hit.

### F20 Personal alerts and monthly report

* FR20.1 Alerts: allocation drift, volatility above user tolerance, goal reached, maturity due (F26), revaluation due (F25), hawl approaching (F13).
* FR20.2 Monthly email report: spending, net worth, Zakat estimate, FIRE progress.

### F21 Community benchmarking (later)

* FR21.1 Opt-in; anonymised aggregates only; show a peer group only when it has at least 50 users.
* FR21.2 Metrics: savings rate, FIRE progress by age band.

### F23 Data privacy controls

* FR23.1 Comply with Bangladesh Personal Data Protection Ordinance 2025: explicit, specific, withdrawable consent; prompt breach notification to the National Data Governance Authority; purpose and retention notices. Confirm gazette status (Q3).
* FR23.2 Religion is sensitive data; Zakat and Shariah preferences require separate explicit consent.
* FR23.3 Encryption in transit (TLS) and at rest; field-level encryption for account numbers and documents; end-to-end encryption only for exports and backups.
* FR23.4 Self-service data export (JSON, CSV) and account deletion within 7 days.
* FR23.5 Anonymised report export that strips account numbers, names and documents.
* FR23.6 GDPR and CCPA readiness for EU and California users (not launch blockers).

### F24 Multi-owner household records

* FR24.1 Household with members; each asset and liability has one or more owners with percentages.
* FR24.2 Roles: `OWNER`, `EDITOR`, `VIEWER`.
* FR24.3 Household dashboard combined; Zakat and tax computed per person.

### F25 Alternative investments

* Asset types: land, flat, plot, rental property, gold and jewellery, private business stake, partnership, agricultural venture (fish, poultry, cattle), private loan given, startup or private equity, collectible, other.
* FR25.1 Fields: type, name, purchase date, cost, ownership shares, counterparty, expected exit or maturity, liquidity (`<1M`, `<1Y`, `>1Y`), notes.
* FR25.2 Valuation: manual with revaluation reminder (6 or 12 months); gold valued from configured price per gram and karat; valuation history kept.
* FR25.3 Cash flows (rent, profit share, instalment, capital added, sale proceeds); return as XIRR.
* FR25.4 Encrypted document attachments (deeds, agreements, receipts).
* FR25.5 Shariah flag per asset with reason (for example, interest-bearing private loan).
* FR25.6 Zakat treatment per asset type from config (section 7.3).
* FR25.7 Feeds F14, F16, F17.
* FR25.8 Co-owners inside or outside the household by percentage.
* FR25.9 Due-diligence checklist for new private deals (registered business, written agreement, promised return vs T-bill yield). No rating or recommendation.

### F26 Sukuk and Islamic bank investments

* Product types: government sukuk (Bangladesh Government Investment Sukuk, Ijarah; example IRIDPNFL, 7 years, 9.60% p.a., half-yearly, min Tk 10,000), DSE-listed corporate sukuk, Mudaraba savings account, Mudaraba term deposit, monthly profit scheme, Mudaraba savings scheme (DPS-style), Hajj savings, cash waqf, Mudaraba perpetual bond. Product names vary by bank; keep a configurable product catalogue.
* FR26.1 Holding fields: issuer or bank, product, amount, start and maturity dates, expected rate, payment frequency, profit received.
* FR26.2 Provisional vs final Mudaraba profit rate; recompute returns when final rate is entered.
* FR26.3 Maturity calendar and reminders; notices of upcoming government sukuk auctions. Since August 2026, 10% of each government sukuk issue is reserved for individual investors.
* FR26.4 Comparison view: expected rates of sukuk and Islamic bank term products vs 91-day T-bill and CPI inflation, showing real return. Information only.
* FR26.5 Bank safety panel: deposit concentration per bank; admin-maintained flag for banks under Bangladesh Bank restructuring, with a note (for example, Sammilito Islami Bank: merger of five Shariah banks in 2025; profit for 2024–25 cut; withdrawals above Tk 2 lakh capped at Tk 1 lakh per quarter for two years).
* FR26.6 Record tax deducted at source on profit (feeds F13).
* FR26.7 Feeds F13, F14, F15, F17.

\---

## 7\. Methodologies (config-driven)

### 7.1 Shariah screening

Two methodologies, both versioned in `config/shariah.yaml`. Values are approximate until approved by the Shariah advisor (Q1).

**Stage 1, business activity (both methods):** fail if core business is conventional banking, conventional insurance, interest-based lending, alcohol, tobacco, pork, gambling, adult entertainment, or weapons. Islamic banks and takaful pass Stage 1. Classification is admin-maintained per company with a reason.

**Stage 2, financial ratios:**

|Ratio|AAOIFI-style threshold|S\&P-style threshold|
|-|-|-|
|Interest-bearing debt ÷ market cap|< 30%|< 33%|
|Cash + interest-bearing securities ÷ market cap|< 30%|< 33%|
|Non-permissible income ÷ total revenue|< 5%|< 5%|
|Receivables ÷ market cap|not used|< 49%|

* Market cap uses a trailing average (S\&P-style: 24 months; AAOIFI-style: config, default 12 months).
* `UNDER\_REVIEW` if any input missing or any ratio within `review\_margin\_pts` (default 2 points) of a threshold.
* Default display: show both results; overall status from `default\_method` (Q1).

### 7.2 Analytics formulas

* Adjusted prices: back-adjust for bonus shares, rights and splits from `corporate\_action`.
* Weekly returns: last trading day of each week (DSE trades Sunday to Thursday).
* XIRR: Newton-Raphson with bisection fallback.
* Time-weighted return: daily linked sub-period returns.
* Volatility: annualised standard deviation of weekly returns × √52.

### 7.3 Zakat rules (`config/zakat.yaml`)

|Asset|Default treatment|
|-|-|
|Cash, bank balances, Islamic deposits|100% of balance|
|Sukuk|Market or face value (config), plus accrued profit received|
|Savings certificates, FDR, DPS|Principal (profit flagged; scholar to confirm treatment of interest)|
|DSE shares|Per method in FR13.3|
|Mutual fund units|Market value (NAV)|
|Gold and silver|Market value by weight and karat|
|Land or property held for resale|Market value|
|Family home, personal car|Exempt|
|Rental property|Exempt asset; saved rental income counted as cash|
|Business stake|Share of business's zakatable assets (or market value if unknown)|
|Private loans given|Counted if recoverable (user toggle)|
|Debts due within the year|Deducted|

Rate 2.5% (lunar year). All rules require advisor approval (Q2).

\---

## 8\. Data sources and ingestion

|Dataset|Source (adapter)|Schedule (Asia/Dhaka)|Notes|
|-|-|-|-|
|EOD prices, volume, indices (DSEX, DSES, DS30)|DSE day-end archive; backfill from public EOD datasets|Trading days 16:30, retry to 18:00|Validate row counts per day|
|Corporate actions|DSE announcements|Daily|Required before computing returns|
|Company master, sector|DSE company pages|Weekly||
|Financial statements|Company annual and quarterly reports (PDF)|Weekly check|Semi-automatic extraction plus manual review queue|
|T-bill and bond auction results|Bangladesh Bank press releases|Daily check|91, 182, 364-day; 2–20 year bonds|
|Policy rate, liquidity, remittance, BDT/USD|Bangladesh Bank|Daily or monthly||
|CPI inflation|Bangladesh Bureau of Statistics|Monthly||
|Brent, LNG prices|Public international data|Daily||
|Gold and silver price per gram|Configured local source or manual admin entry|Daily|For nisab and F25|
|Sukuk issues and auctions|Bangladesh Bank, bank pages|Weekly||
|Islamic bank rate sheets|Bank websites (manual curation)|Monthly||
|Shock events|Admin curation from news|As needed||

**Data quality checks (block publishing on failure):** missing trading days, duplicate rows, price moves over 10% without a corporate action, nulls in required fields, stale source (> 3 trading days). Failed checks create an admin task; the UI shows the last good date.

\---

## 9\. Data model (PostgreSQL)

Use UUID primary keys, `created\_at`/`updated\_at` on every table, and `source\_id` foreign keys on all market data.

**Reference and market data**

* `source` (id, name, url, fetched\_at, checksum)
* `company` (ticker, name, sector, listing\_date, is\_active)
* `price\_daily` (ticker, date, open, high, low, close, volume, adj\_close, source\_id)
* `index\_daily` (index\_code, date, close, source\_id)
* `corporate\_action` (ticker, ex\_date, type, ratio, amount, source\_id)
* `financials` (ticker, period\_end, period\_type, total\_debt\_interest\_bearing, cash\_and\_interest\_securities, receivables, total\_revenue, non\_permissible\_income, zakatable\_assets, shares\_outstanding, source\_id, reviewed\_by, reviewed\_at)
* `business\_classification` (ticker, stage1\_pass, reason, method\_version, set\_by)
* `shariah\_result` (ticker, period\_end, method, method\_version, ratios jsonb, status, reasons jsonb, screened\_at, override\_reason)
* `macro\_series` (series\_code, date, value, source\_id)
* `event` (id, type, t0, title\_en, title\_bn, description, source\_links jsonb, published)
* `score` (ticker\_or\_sector, score\_type, value, std\_error, confidence, n\_obs, sample\_start, sample\_end, computed\_at)
* `event\_metric` (event\_id, ticker\_or\_sector, ret\_1, ret\_5, ret\_20, max\_dd\_60, sessions\_to\_recover)
* `regime\_month` (month, label, components jsonb)
* `sukuk\_issue`, `islamic\_product` (catalogue), `bank\_flag` (bank, status, note, source\_links)
* `config\_version` (domain, version, yaml, approved\_by, approved\_at)

**Users and personal finance**

* `user` (email, password\_hash, locale, consents jsonb), `household`, `household\_member` (role)
* `account` (household\_id, type, institution, masked\_number, encrypted\_number)
* `holding` (account\_id, instrument\_type, ticker or product\_id, quantity, cost, start\_date, maturity\_date, expected\_rate, final\_rate)
* `owner\_share` (asset\_type, asset\_id, member\_id or external\_name, pct)
* `transaction` (holding\_id, date, type, amount, units)
* `alt\_asset` (household\_id, type, name, cost, purchase\_date, liquidity, shariah\_flag, shariah\_reason, zakat\_rule, counterparty)
* `valuation` (asset\_type, asset\_id, date, value, method)
* `cash\_flow` (asset\_id, date, amount, type)
* `document` (asset\_id, encrypted\_blob\_ref, type, uploaded\_at)
* `expense` (member\_id, date, amount, category\_id, note, recurring\_id), `expense\_category`, `recurring\_rule`
* `zakat\_snapshot` (member\_id, date, nisab\_basis, nisab\_value, items jsonb, zakat\_due, config\_version)
* `tax\_snapshot` (member\_id, tax\_year, items jsonb)
* `goal`, `fire\_plan`, `scenario\_result`
* `watchlist`, `alert\_rule`, `notification`
* `firm`, `firm\_seat`, `api\_key`, `api\_usage`
* `subscription` (user\_or\_firm, plan, status, provider\_ref)
* `audit\_log` (actor, action, entity, before, after, at)

\---

## 10\. API (FastAPI, `/api/v1`)

Public (no auth): `GET /companies`, `GET /companies/{ticker}`, `GET /companies/{ticker}/shariah`, `GET /companies/{ticker}/scores`, `GET /shariah/list`, `GET /indices/{code}/series`, `GET /macro/series/{code}`, `GET /macro/notes/{week}`, `GET /events`, `GET /events/{id}`.

Auth: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/reset`, `GET /me`, `PATCH /me/consents`, `GET /me/export`, `DELETE /me`.

Personal (auth, household-scoped): CRUD for `/households`, `/members`, `/accounts`, `/holdings`, `/transactions`, `/alt-assets`, `/valuations`, `/cash-flows`, `/documents`, `/expenses`, `/categories`, `/recurring`, `/goals`, `/alerts`; plus `POST /imports/broker-statement`, `POST /imports/expenses`, `GET /portfolio/summary`, `GET /portfolio/performance`, `GET /portfolio/allocation`, `GET /portfolio/market-check` (F6), `POST /zakat/snapshots`, `POST /tax/snapshots`, `POST /fire/plan`, `POST /fire/scenarios`, `GET /sukuk/calendar`, `GET /islamic-products/compare`.

Firm (API key): `GET /firm/v1/shariah`, `GET /firm/v1/scores`, `GET /firm/v1/events`, `GET /firm/v1/reports/weekly.pdf`.

Admin (role): data review queue, overrides, event curation, config versions, bank flags, macro note publish.

All responses include `as\_of` and `sources` where data-derived. OpenAPI spec generated and committed.

\---

## 11\. Architecture and tech stack

Revised 2026-11-14: the web client moved from Nuxt to Next.js so the later mobile app (F11, Expo / React Native) can share TypeScript code. Reasons are in `docs/DECISIONS.md`.

```
Public sources -> Ingestion jobs (Python, scheduled) -> PostgreSQL <-> Analytics jobs (Python)
                                                          |
                                                    FastAPI backend -> Alerts (email, web push)
                                                          |
                                     Next.js web app (SSR, bn/en)   Expo mobile app (later)
                                                  \________ shared TypeScript packages ________/
```

|Layer|Choice|
|-|-|
|Backend|Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (sync, psycopg 3), Alembic|
|Database|PostgreSQL 16|
|Jobs|Separate worker process with APScheduler; add Redis and a task queue in R2 for alert fan-out|
|Analytics|pandas, numpy, statsmodels|
|PDF extraction|pdfplumber, with a manual review UI|
|Web|Next.js (App Router, React, TypeScript), next-intl (bn, en), Tailwind CSS, Metronic 9 theme (Layout 9), Recharts|
|Mobile (later)|Expo (React Native), reusing `frontend/packages/*`|
|Shared client code|`frontend/packages/core` (BDT and number formatting), `frontend/packages/i18n` (messages), generated API client|
|Auth|httpOnly secure session cookies for web, bearer tokens for mobile; argon2 password hashing|
|Files|S3-compatible object storage, encrypted|
|Email and push|Transactional email provider; Web Push; Expo Notifications later|
|Payments (R2)|SSLCommerz and/or bKash behind a `PaymentProvider` interface; subscriptions stored independently of the provider|
|Dev|Docker Compose; GitHub Actions CI|
|Hosting|Singapore-region server for API, worker and DB (confirm data residency under Q3); web on the same host or a Node host|

**Repo structure**

```
analysisace/
  CLAUDE.md
  docs/ (PRD.md, ARCHITECTURE.md, DECISIONS.md, ROADMAP.md)
  backend/
    app/ (api/, core/, models/, schemas/, services/, analytics/, ingestion/adapters/, jobs/)
    alembic/
    tests/
  frontend/ (npm workspaces)
    apps/web/ (Next.js app)
    apps/mobile/ (Expo app, later)
    packages/core/ (formatting, shared types)
    packages/i18n/ (messages/bn.json, messages/en.json)
  config/ (shariah.yaml, zakat.yaml, regime.yaml, schedules.yaml, excluded\_periods.yaml, trading\_calendar.yaml)
  coming-soon/ (current static page for analysisACE.com)
  docker-compose.yml
```

\---

## 12\. Non-functional requirements

|Area|Requirement|
|-|-|
|Performance|Public pages < 2 s on 4G (LCP); API p95 < 300 ms for precomputed reads; no heavy computation on request|
|Mobile|Mobile-first; usable at 360 px width|
|Language|Full Bangla and English UI; Bangla or Latin digits per user setting; BDT formatting with lakh and crore|
|Time|All dates stored UTC, shown Asia/Dhaka; DSE trading calendar Sunday to Thursday plus holidays in config|
|Availability|99.5% monthly; graceful "last updated" on stale data|
|Accessibility|WCAG 2.1 AA for core pages|
|SEO|SSR public pages per company and event; sitemap; structured data|
|Observability|Structured logs, job run history, alert on failed jobs|
|Backups|Daily encrypted DB backups, 30-day retention, tested restore|

\---

## 13\. Security, privacy, compliance

* OWASP Top 10 controls; rate limiting on auth and public APIs; CSRF protection for cookie sessions.
* Least-privilege DB roles; secrets in environment or secret manager, never in repo.
* Field-level encryption for account numbers and documents; key rotation documented.
* Audit log for admin actions, overrides and config changes.
* Consent records per purpose (marketing, religious-preference features, community benchmarking).
* Legal checks before charging (Q4): BSEC rules on investment advice; DSE data licensing (Q5).
* Disclaimers on all analytical pages, emails and PDFs.

\---

## 14\. Milestones and build plan

### M0 Project setup (week 1)

* Repo scaffold per section 11, Docker Compose, CI (lint, type check, tests), `CLAUDE.md`, base config files, i18n setup.
* DoD: `docker compose up` runs API, worker, DB and frontend; CI green.

### M1 Data foundation (weeks 2–6)

* Adapters and jobs for prices, indices, corporate actions, company master, T-bill auctions, macro series, gold price (manual admin entry acceptable).
* Price adjustment, trading calendar, data quality checks, admin review queue.
* Backfill 5+ years.
* DoD: daily job runs unattended for 10 trading days; quality checks pass; backfill complete.

### M2 MVP (weeks 7–12): F1, F2, F3, F4, F23 basics

* Financial statement extraction for top 100 companies by market cap, then all.
* Shariah screening engine (both methods), company pages, Shariah list, basket vs DSES/DSEX chart.
* Rate sensitivity scores; macro note generator and admin publish.
* Auth, consents, account deletion and export.
* DoD: all ACs in sections 5 and 7 pass; methodology approved by Shariah advisor (Q1); legal check on free pages done.

### M3 Release 2 (months 4–6, before Ramadan 2027): F5, F6, F7, F12, F13, F14, F25 basic, F26 holdings and calendar, payments

* DoD: Zakat worked examples pass; broker CSV import works for at least two brokers; Pro plan purchasable.

### M4 Release 3 (months 7–9): F8, F9, F15, F16, F17, F18, F19, F20, F24, F25 full, F26 comparison and safety panel

* DoD: firm pilot onboarding works end to end (seats, API key, white-label PDF).

### Later: F10, F11, F21, F22, automatic broker connections.

\---

## 15\. Testing strategy

* Unit tests for every formula (screening ratios, regression, event metrics, XIRR, TWR, FIRE, Zakat) with worked examples in `tests/fixtures/`.
* Golden-file tests for screening results on 10 seeded companies.
* Property tests for price adjustment and return calculations.
* API tests for auth scoping (no cross-household access).
* Frontend: Vitest for components; Playwright for key flows (search stock, add holding, Zakat snapshot, FIRE plan) in bn and en.
* Coverage target 80% for `analytics/` and `services/`.

\---

## 16\. Risks

|Risk|Mitigation|
|-|-|
|BSEC treats Pro features as investment advice|Legal opinion before charging; descriptive language only|
|Shariah methodology challenged|Advisor sign-off; publish methodology and changelog|
|Conflict with DSE DSES licence|Independent methodology; never use the DSE list|
|PDF extraction errors|Review queue; `UNDER\_REVIEW` status; user error reports|
|Data source blocks access|Adapter pattern; backfill dataset; licensed feed fallback|
|Low willingness to pay|Firm licences first; test prices early|
|Islamic bank instability affects users|Bank safety panel; neutral, sourced notes|
|Founder time limits|Strict milestone scope; automate jobs early|

\---

## 17\. Open questions (with defaults to build against)

|ID|Question|Default until answered|
|-|-|-|
|Q1|AAOIFI-style, S\&P-style, or both for overall status? Who is the Shariah advisor?|Compute both; overall status uses AAOIFI-style|
|Q2|Zakat method for shares and treatment of interest-bearing savings|`MARKET\_VALUE` default; flag interest-bearing items for user decision|
|Q3|Is the Personal Data Protection Ordinance 2025 gazetted, and from when?|Comply fully from launch|
|Q4|Is a BSEC licence needed for Pro or Firm plans?|Ship paid plans behind a feature flag, off until cleared|
|Q5|Can DSE day-end data be stored and shown commercially?|Store; show own analysis and prices with attribution; adapter ready for licensed feed|
|Q6|Crypto: drop entirely or manual entry for users abroad?|Generic "other asset" only|
|Q7|Personal finance in the same app or a separate app?|Same app, separate navigation section|
|Q8|Pricing (Pro Tk 300–500/month; Firm Tk 1.5–3 lakh/year)|Prices in config; Pro off until Q4|
|Q9|Gold and silver price source|Manual daily admin entry|
|Q10|Brand: analysisACE or a Shariah sub-brand?|analysisACE|

\---

## Appendix A: `CLAUDE.md`

The live file is `CLAUDE.md` at the repo root, with `backend/CLAUDE.md` and `frontend/CLAUDE.md` for area-specific rules. Keep the rules below in the root file:

* Never give investment advice: no buy/sell/hold, targets or signals. Use descriptive wording.
* Never store or show the DSE DSES constituent list.
* No crypto integrations.
* Thresholds, Zakat rules, schedules: only in config/\*.yaml, versioned.
* Every data-derived API response includes `as\_of` and `sources`.
* Money in BDT as integer paisa or Decimal, never float.
* Dates stored UTC, shown Asia/Dhaka; DSE trades Sunday to Thursday.
* All user-facing strings go through i18n (bn, en).
* Reference PRD requirement IDs (e.g. FR13.2) in tests and commits.
* Add or update tests with every change to analytics/ or services/.

\---

## Appendix B: Glossary

|Term|Meaning|
|-|-|
|DSE, DSEX, DS30, DSES|Dhaka Stock Exchange; its broad index; its blue-chip index; its Shariah index|
|BO account|Beneficiary owner account for holding shares|
|T-bill|Government treasury bill (91, 182, 364 days)|
|Sukuk|Shariah-compliant certificate of ownership in assets; pays rent or profit, not interest|
|Ijarah|Lease-based sukuk structure|
|Mudaraba|Profit-sharing contract used by Islamic bank deposits|
|Nisab|Minimum wealth for Zakat (87.48 g gold or 612.36 g silver)|
|Hawl|One lunar year of holding wealth before Zakat is due|
|Purification|Giving away the non-permissible share of dividends|
|Sanchayapatra|Government savings certificates|
|FDR, DPS|Fixed deposit receipt; deposit pension scheme (monthly savings)|
|FIRE|Financial independence, retire early|
|XIRR|Annualised return for irregular cash flows|

\---

## Appendix C: References

* Planning docs: DSE Macro Analysis Plan (claude.ai artifact KGmA4mWjx3iovpBPBB22Z5); analysisACE PRD living doc (claude.ai artifact SDBXksnePUh9WwPWRmewEv).
* DSES data access: The Financial Express, "DSE's aim to sell Shariah index data fails investors" (Mar 2023).
* Rates: Ekush WML, "Bangladesh's interest rate cycle" (Sep 2026); TOB, "T-bill yields fall below 8% after three years" (Oct 2026).
* War shock: The Financial Express, "Stocks log another worst day in six years" (Mar 2026).
* Sukuk: Prime Bank, IRIDPNFL sukuk page; Dhaka Tribune, "BB reserves 10% sukuk quota for individual" (Aug 2026).
* Islamic bank merger: The Daily Star (Oct 2025); UNB (Jan 2026); Ittefaq (Jan 2026).
* Crypto status: Dhaka Tribune, "Young Bangladeshis turn to cryptocurrency despite legal ban" (Jan 2026).
* Data protection: The Daily Star, "Personal Data Protection Ordinance 2025: key takeaways" (Oct 2025).
* Zakat nisab: bdnews24 (Apr 2024); The Financial Express, "Setting national zakat guidelines" (Apr 2023).
* Shariah fund prospectus example: HFAML Shariah Unit Fund prospectus (Dec 2021).

