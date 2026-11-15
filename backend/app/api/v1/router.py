from fastapi import APIRouter

from app.api.v1 import admin_users, auth, companies, me, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(companies.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin_users.router)
