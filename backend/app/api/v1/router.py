from fastapi import APIRouter

from app.api.v1 import (
    admin_market,
    admin_users,
    alerts,
    assets,
    auth,
    companies,
    costs,
    email_links,
    firm_api,
    firms,
    households,
    income,
    market,
    me,
    planning,
    portfolio,
    push,
    setup,
    system,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(companies.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(push.router)
api_router.include_router(email_links.router)
# Firm features (F9, D30); every route is 404 while FIRM_FEATURES_ENABLED is off.
api_router.include_router(firms.router)
api_router.include_router(firm_api.router)
api_router.include_router(admin_users.router)
# Market layer (F1 to F8).
api_router.include_router(market.router)
api_router.include_router(admin_market.router)
api_router.include_router(watchlist.router)
# Personal finance (F12 to F26).
api_router.include_router(households.router)
api_router.include_router(costs.router)
api_router.include_router(income.router)
api_router.include_router(setup.router)
api_router.include_router(portfolio.router)
api_router.include_router(assets.router)
api_router.include_router(planning.router)
api_router.include_router(alerts.router)
