"""Антиспам без капчі: підписаний токен форми, мінімальний час заповнення, honeypot, ліміт на IP."""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque


class SpamError(Exception):
    """Заявку відхилено. message — внутрішня причина (для логів), користувачу показуємо загальний текст."""


def issue_token(secret: str, now: float | None = None) -> str:
    ts = str(int(now if now is not None else time.time()))
    sig = hmac.new(secret.encode(), ts.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{ts}.{sig}"


def check_token(token: str, secret: str, min_age: float, max_age: float, now: float | None = None) -> None:
    """Токен видається, коли сторінка відкрилась. Бот, що одразу шле POST, не пройде за часом."""
    now = now if now is not None else time.time()
    try:
        ts, sig = token.split(".", 1)
        issued = int(ts)
    except (ValueError, AttributeError):
        raise SpamError("bad token format")
    good = hmac.new(secret.encode(), ts.encode(), hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(sig, good):
        raise SpamError("bad token signature")
    age = now - issued
    if age < min_age:
        raise SpamError(f"form filled too fast ({age:.1f}s)")
    if age > max_age:
        raise SpamError("token expired")


class RateLimiter:
    """Ковзне вікно в пам'яті. Для одного сервера достатньо; для кількох — Redis."""

    def __init__(self, limit: int, window_sec: float = 3600):
        self.limit, self.window = limit, window_sec
        self.hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True
