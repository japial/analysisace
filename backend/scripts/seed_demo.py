"""Loads the full demo data set into a development database.

    python scripts/seed_demo.py

Everything it adds is fictional and labelled as demo data: 13 "Demo" companies with five
years of synthetic prices, indices and macro series, financial statements, shock events,
sukuk and Islamic bank products, plus a demo household, an analyst, a broker firm and an
admin. The household also gets FIRE plans, what-ifs, Zakat and tax statements, notices and
55 opted-in demo peers for the community comparison (app/seed/demo_extras.py).
See app/seed/ for exactly what is created. Safe to run twice; refuses to run outside
development. To start over, stop the database and delete backend/.pgdata.

Demo sign-ins use the password in DEMO_PASSWORD (default: demo-pass-1234).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.trading_calendar import get_trading_calendar
from app.seed.demo_extras import ADMIN_EMAIL, seed_demo_extras
from app.seed.demo_market import END as market_end
from app.seed.demo_market import seed_demo_market
from app.seed.demo_personal import ANALYST_EMAIL, DEMO_EMAIL, FIRM_EMAIL, seed_demo_personal
from app.seed.reference import seed_reference
from app.services.email import get_email_sender
from app.services.macro_notes import generate_draft
from app.services.market_pipeline import run_market_analytics


def main() -> int:
    if get_settings().environment != "development":
        print("Refusing to seed demo data: ENVIRONMENT is not 'development'.")
        return 1
    password = os.environ.get("DEMO_PASSWORD", "demo-pass-1234")

    with get_sessionmaker()() as session:
        added = seed_reference(session)
        print(f"Reference data: {added} default expense categories added.")

        market = seed_demo_market(session, get_trading_calendar())
        print("Market demo data:", market or "already present.")

        personal = seed_demo_personal(session, password)
        session.commit()

        # Screening, scores, event metrics, basket and regime are computed, never seeded.
        analytics = run_market_analytics(session, get_email_sender())
        print("Market analytics:", analytics)
        if market:
            generate_draft(session, market_end)
        session.commit()

        # Plans, Zakat, tax, notices and peers come from the app's own services (F13 to F21).
        extras = seed_demo_extras(session, get_email_sender(), password)
        session.commit()
        print("Plans, statements, notices and peers:", extras.counts or "already present.")
        if personal.created:
            print("Personal demo data:", personal.counts)
            print(f"\nSign in with password {password!r}:")
            print(f"  {DEMO_EMAIL}     household owner, Pro plan")
            print(f"  {ANALYST_EMAIL}  analyst role")
            print(f"  {FIRM_EMAIL}     admin of Demo Brokerage Ltd.")
            print(f"  {ADMIN_EMAIL}    admin role (admin screens)")
            print(f"\nFirm API key (shown once): {personal.firm_api_key}")
        else:
            print("Personal demo data: already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
