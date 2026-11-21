from fastapi import APIRouter

from app.api.v1 import (
    admin_market,
    admin_users,
    alerts,
    assets,
    auth,
    companies,
    costs,
    households,
    market,
    me,
    planning,
    portfolio,
    system,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(companies.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin_users.router)
# Market layer (F1 to F8).
api_router.include_router(market.router)
api_router.include_router(admin_market.router)
api_router.include_router(watchlist.router)
# Personal finance (F12 to F26).
api_router.include_router(households.router)
api_router.include_router(costs.router)
api_router.include_router(portfolio.router)
api_router.include_router(assets.router)
api_router.include_router(planning.router)
api_router.include_router(alerts.router)
