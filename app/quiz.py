"""Quiz content: one source of truth for the frontend (GET /api/quiz) and for server-side validation."""
from __future__ import annotations

APPLIANCES: dict[str, dict] = {
    "refrigerator": {"label": "Refrigerator", "icon": "fridge",
                     "problems": ["Not cooling", "Leaking water", "Ice maker not working", "Loud or unusual noise",
                                  "Freezer frosting up"]},
    "washer": {"label": "Washer", "icon": "washer",
               "problems": ["Won't drain", "Won't spin", "Leaking", "Won't start", "Shaking / loud"]},
    "dryer": {"label": "Dryer", "icon": "dryer",
              "problems": ["Not heating", "Won't tumble", "Takes too long to dry", "Won't start", "Squeaking / noise"]},
    "dishwasher": {"label": "Dishwasher", "icon": "dishwasher",
                   "problems": ["Not cleaning well", "Won't drain", "Leaking", "Won't start", "Error code"]},
    "oven": {"label": "Oven / Range", "icon": "oven",
             "problems": ["Not heating", "Burner won't light", "Temperature is off", "Door won't close", "Error code"]},
    "other": {"label": "Something else", "icon": "other",
              "problems": ["Not working at all", "Making noise", "Leaking", "Error code"]},
}
OTHER_PROBLEM = "Other / not sure"

BRANDS = ["Whirlpool", "Samsung", "LG", "GE", "Frigidaire", "Maytag", "Bosch", "KitchenAid", "Other / not sure"]
AGES = ["Less than 3 years", "3–7 years", "8+ years", "Not sure"]
URGENCY = {"asap": "Today — as soon as possible", "tomorrow": "Tomorrow", "week": "This week",
           "quote": "Just getting a quote"}


def problems_for(appliance: str) -> list[str]:
    return APPLIANCES[appliance]["problems"] + [OTHER_PROBLEM]


def public_config() -> dict:
    return {
        "appliances": [{"id": k, "label": v["label"], "icon": v["icon"], "problems": problems_for(k)}
                       for k, v in APPLIANCES.items()],
        "brands": BRANDS,
        "ages": AGES,
        "urgency": [{"id": k, "label": v} for k, v in URGENCY.items()],
    }
