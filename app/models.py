"""Валідація заявки. Усі відповіді квізу перевіряються за тим самим списком, що бачить фронтенд."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from .quiz import AGES, APPLIANCES, BRANDS, URGENCY, problems_for

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


def normalize_us_phone(raw: str) -> str:
    """'(512) 555-0123', '512.555.0123', '+1 512 555 0123' → '+15125550123'. Некоректний → ValueError."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Enter a 10-digit US phone number")
    if digits[0] in "01" or digits[3] in "01":  # NANP: код зони і станції не починаються з 0/1
        raise ValueError("This doesn't look like a valid US phone number")
    if len(set(digits)) == 1:
        raise ValueError("This doesn't look like a valid US phone number")
    return "+1" + digits


def pretty_phone(e164: str) -> str:
    d = e164[-10:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}"


class UTM(BaseModel):
    source: str = Field("", max_length=100)
    medium: str = Field("", max_length=100)
    campaign: str = Field("", max_length=150)
    term: str = Field("", max_length=150)
    content: str = Field("", max_length=150)
    gclid: str = Field("", max_length=200)


class LeadIn(BaseModel):
    appliance: str
    problem: str
    brand: str
    age: str
    urgency: str
    zip: str
    name: str = Field(min_length=2, max_length=80)
    phone: str
    email: str = Field("", max_length=120)
    consent: bool
    utm: UTM = Field(default_factory=UTM)
    page_url: str = Field("", max_length=500)
    form_token: str = ""
    website: str = ""  # пастка для ботів: поле приховане, людина його не бачить

    @field_validator("appliance")
    @classmethod
    def _appliance(cls, v):
        if v not in APPLIANCES:
            raise ValueError("Unknown appliance")
        return v

    @field_validator("brand")
    @classmethod
    def _brand(cls, v):
        if v not in BRANDS:
            raise ValueError("Unknown brand")
        return v

    @field_validator("age")
    @classmethod
    def _age(cls, v):
        if v not in AGES:
            raise ValueError("Unknown age")
        return v

    @field_validator("urgency")
    @classmethod
    def _urgency(cls, v):
        if v not in URGENCY:
            raise ValueError("Unknown urgency")
        return v

    @field_validator("zip")
    @classmethod
    def _zip(cls, v):
        v = v.strip()[:5]
        if not re.fullmatch(r"\d{5}", v):
            raise ValueError("Enter a 5-digit ZIP code")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = " ".join(v.split())
        if not re.search(r"[A-Za-zÀ-ÿ]", v) or re.search(r"https?://|www\.|<|>", v, re.I):
            raise ValueError("Please enter your name")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return normalize_us_phone(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if v and not _EMAIL.match(v):
            raise ValueError("Enter a valid email or leave it empty")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v):
        if not v:
            raise ValueError("Please agree to be contacted")
        return v

    @model_validator(mode="after")
    def _problem_matches_appliance(self):
        if self.problem not in problems_for(self.appliance):
            raise ValueError("Unknown problem for this appliance")
        return self
