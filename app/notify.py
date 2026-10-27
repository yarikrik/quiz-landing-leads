"""Доставка заявки: Telegram (обов'язково) і Google Sheets (якщо налаштовано), з повторними спробами."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import httpx

from .config import Settings
from .models import pretty_phone
from .quiz import APPLIANCES, URGENCY
from .storage import LeadStore

log = logging.getLogger(__name__)

ICONS = {"refrigerator": "🧊", "washer": "🫧", "dryer": "🌀", "dishwasher": "🍽", "oven": "🔥", "other": "🔧"}
URGENT = {"asap": "🚨", "tomorrow": "⏱", "week": "📅", "quote": "💬"}
SHEET_HEADER = ["ID", "Date", "Appliance", "Problem", "Brand", "Age", "When", "ZIP", "In area",
                "Name", "Phone", "Email", "UTM source", "UTM medium", "UTM campaign", "UTM term", "GCLID", "Page"]


def local_time(lead: dict, tz: str) -> datetime:
    return datetime.fromisoformat(lead["created_at"]).astimezone(ZoneInfo(tz))


def format_lead(lead: dict, tz: str = "America/Chicago") -> str:
    e = lambda s: escape(str(s), quote=False)  # noqa: E731
    area = "✅ in service area" if lead["in_area"] else "⚠️ OUTSIDE service area"
    lines = [
        f"{URGENT[lead['urgency']]} <b>New lead #{lead['id']}</b> — {e(URGENCY[lead['urgency']])}",
        "",
        f"{ICONS[lead['appliance']]} <b>{e(APPLIANCES[lead['appliance']]['label'])}</b>: {e(lead['problem'])}",
        f"🏷 {e(lead['brand'])} · {e(lead['age'])}",
        f"📍 ZIP {lead['zip']} — {area}",
        "",
        f"👤 {e(lead['name'])}",
        f"📞 <code>{pretty_phone(lead['phone'])}</code>",
    ]
    if lead["email"]:
        lines.append(f"✉️ {e(lead['email'])}")
    utm = {k: v for k, v in lead["utm"].items() if v and k != "gclid"}
    if utm or lead["utm"].get("gclid"):
        src = " / ".join(e(utm[k]) for k in ("source", "medium", "campaign", "term") if utm.get(k))
        lines += ["", f"📈 {src or 'Google Ads'}" + (" · gclid ✓" if lead["utm"].get("gclid") else "")]
    lines.append(f"🕒 {local_time(lead, tz):%b %d, %I:%M %p}")
    return "\n".join(lines)


def sheet_row(lead: dict, tz: str = "America/Chicago") -> list:
    u = lead["utm"]
    return [lead["id"], local_time(lead, tz).strftime("%Y-%m-%d %H:%M"), APPLIANCES[lead["appliance"]]["label"],
            lead["problem"], lead["brand"], lead["age"], URGENCY[lead["urgency"]], lead["zip"],
            "yes" if lead["in_area"] else "no", lead["name"], pretty_phone(lead["phone"]), lead["email"],
            u.get("source", ""), u.get("medium", ""), u.get("campaign", ""), u.get("term", ""), u.get("gclid", ""),
            lead["page_url"]]


async def send_telegram(settings: Settings, text: str, client: httpx.AsyncClient) -> None:
    r = await client.post(f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                          json={"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=15)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram: {data.get('description', r.status_code)}")


class SheetsWriter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._ws = None

    def _worksheet(self):
        if self._ws is None:
            import gspread
            sh = gspread.service_account(filename=str(self.settings.google_credentials)).open_by_key(self.settings.sheet_id)
            ws = sh.sheet1
            if ws.row_values(1) != SHEET_HEADER:
                ws.update(range_name="A1", values=[SHEET_HEADER])
            self._ws = ws
        return self._ws

    def append(self, row: list) -> None:
        self._worksheet().append_row(row, value_input_option="USER_ENTERED")


class Notifier:
    def __init__(self, settings: Settings, store: LeadStore, client: httpx.AsyncClient | None = None,
                 sheets: SheetsWriter | None = None, retries: int = 3, backoff: float = 2.0,
                 timezone: str = "America/Chicago"):
        self.settings, self.store = settings, store
        self.client = client or httpx.AsyncClient()
        self.sheets = sheets if sheets is not None else (SheetsWriter(settings) if settings.sheet_id else None)
        self.retries, self.backoff, self.tz = retries, backoff, timezone

    async def _try(self, what: str, fn) -> str | None:
        for attempt in range(1, self.retries + 1):
            try:
                await fn()
                return None
            except Exception as e:
                log.warning("%s failed (attempt %d/%d): %s", what, attempt, self.retries, e)
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * attempt)
                err = f"{what}: {e}"
        return err

    async def deliver(self, lead_id: int) -> None:
        lead = self.store.get(lead_id)
        errors = []
        if not lead["telegram_ok"] and self.settings.telegram_token:
            err = await self._try("telegram", lambda: send_telegram(self.settings, format_lead(lead, self.tz), self.client))
            if err:
                errors.append(err)
            else:
                self.store.mark(lead_id, telegram_ok=1)
        if self.sheets and not lead["sheets_ok"]:
            err = await self._try("sheets", lambda: asyncio.to_thread(self.sheets.append, sheet_row(lead, self.tz)))
            if err:
                errors.append(err)
            else:
                self.store.mark(lead_id, sheets_ok=1)
        self.store.mark(lead_id, last_error="; ".join(errors))
        if errors:
            log.error("Lead #%s not fully delivered: %s", lead_id, errors)

    async def redeliver_pending(self) -> int:
        pending = [lead["id"] for lead in self.store.undelivered()]
        for lead_id in pending:
            await self.deliver(lead_id)
        return len(pending)
