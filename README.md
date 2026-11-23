# analysisACE

Personal finance for Bangladeshi households, built around **ACE**: **Assets** (what you own and owe, Zakat, wealth statement), **Capital** (portfolio, sukuk, deposits, FIRE and goals) and **Earnings** (income, costs, savings, tax). Includes optional tools for Dhaka Stock Exchange shares: Shariah screening and macro analytics.

| Folder | What it holds |
|-|-|
| `backend/` | FastAPI API, analytics, data ingestion and scheduled jobs (Python 3.12, PostgreSQL 16) |
| `frontend/` | Next.js web app and shared TypeScript packages (npm workspaces) |
| `config/` | Versioned YAML rules: Shariah thresholds, Zakat, schedules, trading calendar |
| `docs/` | Product requirements, architecture, decisions, roadmap |
| `coming-soon/` | Static page currently live on analysisACE.com |

Setup and commands are in [CLAUDE.md](CLAUDE.md). The product spec is [docs/PRD.md](docs/PRD.md).

Historical analysis for education only. Not investment advice.
