"""FastAPI application. Run with `uvicorn app.main:app`."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.auth import AuthError
from app.services.email import check_email_settings


def _auth_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Turns an AuthError into `{"detail": "<CODE>"}`. Clients translate the code."""
    assert isinstance(exc, AuthError)
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse({"detail": exc.code}, status_code=exc.status_code, headers=headers)


def create_app() -> FastAPI:
    settings = get_settings()
    check_email_settings(settings)
    app = FastAPI(
        title="analysisACE API",
        version="0.1.0",
        description="Historical analysis for education only. Not investment advice.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AuthError, _auth_error_handler)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
