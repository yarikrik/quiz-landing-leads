"""API-тести: python -m pytest. Telegram підмінено httpx.MockTransport, Google Sheets — фейком."""
import time
import unittest

try:
    import httpx
    from fastapi.testclient import TestClient
except ImportError:
    httpx = None

from app.antispam import RateLimiter, SpamError, check_token, issue_token
from app.config import Settings
from app.models import normalize_us_phone, pretty_phone

SECRET = "test-secret"


class PhoneTest(unittest.TestCase):
    def test_normalize(self):
        for raw in ("(512) 555-0123", "512.555.0123", "+1 512 555 0123", "15125550123"):
            self.assertEqual(normalize_us_phone(raw), "+15125550123")
        for bad in ("555-0123", "(012) 555-0123", "(512) 155-0123", "222-222-2222", "", "+44 20 7946 0958"):
            with self.assertRaises(ValueError, msg=bad):
                normalize_us_phone(bad)
        self.assertEqual(pretty_phone("+15125550123"), "(512) 555-0123")


class AntispamTest(unittest.TestCase):
    def test_token(self):
        now = 1_800_000_000
        t = issue_token(SECRET, now)
        check_token(t, SECRET, 4, 3600, now + 10)
        with self.assertRaises(SpamError):
            check_token(t, SECRET, 4, 3600, now + 1)       # занадто швидко
        with self.assertRaises(SpamError):
            check_token(t, SECRET, 4, 3600, now + 7200)    # протермінований
        with self.assertRaises(SpamError):
            check_token(t, "other-secret", 4, 3600, now + 10)
        with self.assertRaises(SpamError):
            check_token("garbage", SECRET, 4, 3600, now)

    def test_rate_limiter(self):
        rl = RateLimiter(2, 60)
        self.assertTrue(rl.hit("ip", 0))
        self.assertTrue(rl.hit("ip", 1))
        self.assertFalse(rl.hit("ip", 2))
        self.assertTrue(rl.hit("other", 2))
        self.assertTrue(rl.hit("ip", 62))                   # вікно зсунулось

    def test_service_area(self):
        s = Settings(service_zips=["787*", "78610"])
        self.assertTrue(s.in_service_area("78704"))
        self.assertTrue(s.in_service_area("78610"))
        self.assertFalse(s.in_service_area("78611"))
        self.assertTrue(Settings().in_service_area("10001"))  # порожній список — приймаємо всі


@unittest.skipIf(httpx is None, "fastapi/httpx не встановлено")
class ApiTest(unittest.TestCase):
    def setUp(self):
        from app.main import create_app
        from app.notify import Notifier
        from app.storage import LeadStore

        self.sent, self.rows, self.tg_fail = [], [], False

        def telegram(request: httpx.Request):
            if self.tg_fail:
                return httpx.Response(200, json={"ok": False, "description": "Bad Gateway"})
            self.sent.append(__import__("json").loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {}})

        test = self

        class FakeSheets:
            def append(self, row):
                test.rows.append(row)

        self.settings = Settings(telegram_token="1:T", telegram_chat_id="-100", service_zips=["787*"],
                                 secret_key=SECRET, rate_limit_per_hour=3, sheet_id="x")
        self.store = LeadStore(":memory:")
        client = httpx.AsyncClient(transport=httpx.MockTransport(telegram))
        self.notifier = Notifier(self.settings, self.store, client=client, sheets=FakeSheets(), retries=2, backoff=0)
        self.client = TestClient(create_app(self.settings, self.store, self.notifier))

    def lead(self, **kw):
        data = dict(appliance="refrigerator", problem="Not cooling", brand="Samsung", age="3–7 years", urgency="asap",
                    zip="78704", name="John  Smith", phone="(512) 555-0123", email="John@Example.com", consent=True,
                    utm={"source": "google", "medium": "cpc", "campaign": "fridge-repair", "gclid": "abc"},
                    page_url="https://example.com/?utm_source=google", website="",
                    form_token=issue_token(SECRET, time.time() - 30))
        data.update(kw)
        return data

    def post(self, **kw):
        return self.client.post("/api/leads", json=self.lead(**kw))

    def test_static_and_config(self):
        self.assertIn("FixRight", self.client.get("/").text)
        cfg = self.client.get("/api/quiz").json()
        self.assertEqual(cfg["appliances"][0]["id"], "refrigerator")
        self.assertIn("Other / not sure", cfg["appliances"][0]["problems"])
        self.assertEqual(self.client.get("/api/zip/78704").json()["in_area"], True)
        self.assertEqual(self.client.get("/api/zip/10001").json()["in_area"], False)
        self.assertEqual(self.client.get("/api/zip/abc").json()["valid"], False)
        token = self.client.get("/api/token").json()["token"]
        self.assertRegex(token, r"^\d+\.[0-9a-f]{24}$")

    def test_lead_saved_and_delivered(self):
        r = self.post()
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"] and body["in_area"])
        lead = self.store.get(body["id"])
        self.assertEqual((lead["phone"], lead["name"], lead["email"]), ("+15125550123", "John Smith", "john@example.com"))
        self.assertEqual((lead["telegram_ok"], lead["sheets_ok"], lead["last_error"]), (1, 1, ""))
        text = self.sent[0]["text"]
        for part in ("New lead #1", "Refrigerator", "Not cooling", "(512) 555-0123", "in service area", "google / cpc"):
            self.assertIn(part, text)
        self.assertEqual(self.sent[0]["chat_id"], "-100")
        self.assertEqual(self.rows[0][10], "(512) 555-0123")
        self.assertEqual(self.rows[0][16], "abc")

    def test_outside_area_is_flagged_not_rejected(self):
        r = self.post(zip="10001", phone="212-555-0199")
        self.assertEqual(r.json()["in_area"], False)
        self.assertIn("OUTSIDE service area", self.sent[0]["text"])

    def test_validation_errors(self):
        r = self.post(phone="555-0123", consent=False, problem="Won't drain", email="nope")
        self.assertEqual(r.status_code, 422)
        errors = r.json()["errors"]
        self.assertIn("phone", errors)
        self.assertIn("consent", errors)
        self.assertIn("email", errors)
        r = self.post(problem="Won't drain")  # несправність від пральної машини, а техніка — холодильник
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.store.undelivered(), [])
        self.assertEqual(self.sent, [])

    def test_honeypot_and_token(self):
        r = self.post(website="http://spam.example")
        self.assertEqual(r.json(), {"ok": True, "id": 0, "in_area": True})
        self.assertEqual(self.post(form_token="").status_code, 400)
        self.assertEqual(self.post(form_token=issue_token(SECRET)).status_code, 400)  # заповнено за 0 секунд
        self.assertEqual(self.post(form_token=issue_token("wrong", time.time() - 30)).status_code, 400)
        self.assertIsNone(self.store.get(1))
        self.assertEqual(self.sent, [])

    def test_duplicate_submit_is_idempotent(self):
        first = self.post().json()["id"]
        second = self.post(name="John S.").json()
        self.assertEqual(second["id"], first)
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(self.sent), 1)

    def test_rate_limit(self):
        codes = [self.post(phone=f"512-555-01{i:02d}").status_code for i in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])

    def test_telegram_down_then_redelivered(self):
        self.tg_fail = True
        lead_id = self.post().json()["id"]
        lead = self.store.get(lead_id)
        self.assertEqual(lead["telegram_ok"], 0)
        self.assertIn("Bad Gateway", lead["last_error"])
        self.assertEqual(lead["sheets_ok"], 1)          # таблиця не залежить від Telegram
        self.tg_fail = False
        with TestClient(self.client.app):               # при старті сервер дошле те, що не дійшло
            pass
        self.assertEqual(self.store.get(lead_id)["telegram_ok"], 1)
        self.assertEqual(len(self.rows), 1)             # у таблицю повторно не пишемо


if __name__ == "__main__":
    unittest.main()
