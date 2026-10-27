"""FastAPI: віддає лендинг і приймає заявки.

Запуск: uvicorn app.main:create_app --factory
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .antispam import RateLimiter, SpamError, check_token, issue_token
from .config import Settings, load_settings
from .models import LeadIn
from .notify import Notifier
from .quiz import public_config
from .storage import LeadStore

log = logging.getLogger("leads")
WEB = Path(__file__).resolve().parent.parent / "web"
GENERIC_ERROR = "Something went wrong. Please refresh the page and try again, or give us a call."


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy and (fwd := request.headers.get("x-forwarded-for")):
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def create_app(settings: Settings | None = None, store: LeadStore | None = None,
               notifier: Notifier | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = settings or load_settings()
    store = store or LeadStore(settings.db_path)
    notifier = notifier or Notifier(settings, store, timezone=settings.timezone)
    limiter = RateLimiter(settings.rate_limit_per_hour)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        n = await notifier.redeliver_pending()  # заявки, які не дійшли до Telegram до перезапуску
        if n:
            log.info("Re-delivered %d pending leads", n)
        yield

    app = FastAPI(title="Quiz landing leads", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.store, app.state.notifier = store, notifier

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors: dict[str, str] = {}
        for err in exc.errors():
            loc = [str(x) for x in err["loc"] if x != "body"]
            field = loc[0] if loc else "form"
            msg = err["msg"].removeprefix("Value error, ")
            errors.setdefault(field, msg)
        return JSONResponse({"ok": False, "errors": errors}, status_code=422)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/quiz")
    async def quiz():
        return public_config()

    @app.get("/api/token")
    async def token():
        return {"token": issue_token(settings.secret_key)}

    @app.get("/api/zip/{zip_code}")
    async def zip_check(zip_code: str):
        valid = zip_code.isdigit() and len(zip_code) == 5
        return {"zip": zip_code, "valid": valid, "in_area": valid and settings.in_service_area(zip_code)}

    @app.post("/api/leads")
    async def create_lead(lead: LeadIn, request: Request, background: BackgroundTasks):
        ip = client_ip(request, settings.trust_proxy)
        if lead.website:  # honeypot заповнений — це бот; відповідаємо «успіх», щоб не підказувати
            log.info("Honeypot triggered from %s", ip)
            return {"ok": True, "id": 0, "in_area": True}
        try:
            check_token(lead.form_token, settings.secret_key, settings.min_fill_seconds, settings.token_ttl_seconds)
        except SpamError as e:
            log.info("Rejected lead from %s: %s", ip, e)
            return JSONResponse({"ok": False, "error": GENERIC_ERROR}, status_code=400)

        if (dup := store.recent_by_phone(lead.phone, settings.duplicate_window_minutes)) is not None:
            return {"ok": True, "id": dup, "in_area": settings.in_service_area(lead.zip), "duplicate": True}
        if not limiter.hit(ip):
            return JSONResponse({"ok": False, "error": "Too many requests. Please call us instead."}, status_code=429)

        in_area = settings.in_service_area(lead.zip)
        lead_id = store.add(lead, in_area, ip)
        background.add_task(notifier.deliver, lead_id)
        log.info("Lead #%s saved (%s, %s)", lead_id, lead.appliance, lead.zip)
        return {"ok": True, "id": lead_id, "in_area": in_area}

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app

