"""Application factory: wires the database, session middleware, API and web UI together."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from fairshare.api.routes import router as api_router
from fairshare.config import Settings
from fairshare.db import Database
from fairshare.web.routes import router as web_router

_PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None, *, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="FairShare", version="0.1.0", description="Shared-expense tracker.")

    db = database or Database(settings.database_url)
    db.create_all()
    app.state.db = db
    app.state.settings = settings

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie,
        same_site="lax",
        https_only=False,
    )

    app.mount("/static", StaticFiles(directory=_PACKAGE_DIR / "static"), name="static")
    app.include_router(api_router)
    app.include_router(web_router)

    @app.exception_handler(StarletteHTTPException)
    async def _auth_redirect(request: Request, exc: StarletteHTTPException):
        # Send logged-out browsers to the login page; keep JSON errors for the API.
        if exc.status_code == 401 and not request.url.path.startswith("/api"):
            return RedirectResponse("/", status_code=303)
        return await http_exception_handler(request, exc)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
