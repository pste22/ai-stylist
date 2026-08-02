"""Indian festival calendar — proactive occasion nudges for Mira."""
from datetime import date

# (name, date, occasion_type, look_hint)
# occasion_type maps to look_engine buckets
FESTIVALS = [
    # 2025
    ("Navratri",      date(2025, 9, 22),  "festive",  "Garba / chaniya choli"),
    ("Dussehra",      date(2025, 10, 2),  "festive",  "ethnic festive"),
    ("Dhanteras",     date(2025, 10, 20), "festive",  "festive ethnic"),
    ("Diwali",        date(2025, 10, 20), "festive",  "Diwali party / ethnic glam"),  # same day as Dhanteras sometimes
    ("Bhai Dooj",     date(2025, 10, 23), "festive",  "festive ethnic"),
    ("Christmas",     date(2025, 12, 25), "party",    "festive western"),
    ("New Year Eve",  date(2025, 12, 31), "party",    "party / cocktail"),
    # 2026
    ("Holi",          date(2026, 3, 6),   "festive",  "fun colourful casual"),
    ("Eid",           date(2026, 3, 20),  "festive",  "ethnic festive"),
    ("Navratri",      date(2026, 9, 20),  "festive",  "Garba / chaniya choli"),  # approximate
    ("Dussehra",      date(2026, 10, 1),  "festive",  "ethnic festive"),
    ("Dhanteras",     date(2026, 10, 18), "festive",  "festive ethnic"),
    ("Diwali",        date(2026, 10, 20), "festive",  "Diwali party / ethnic glam"),
    ("Bhai Dooj",     date(2026, 10, 22), "festive",  "festive ethnic"),
    ("Christmas",     date(2026, 12, 25), "party",    "festive western"),
    ("New Year Eve",  date(2026, 12, 31), "party",    "party / cocktail"),
    # 2027
    ("Holi",          date(2027, 3, 25),  "festive",  "fun colourful casual"),
]

def upcoming_festival(within_days: int = 21):
    """Return (name, days_away, occasion_type, look_hint) or (None, None, None, None)."""
    today = date.today()
    soonest = None
    soonest_delta = within_days + 1
    for name, d, occ, hint in FESTIVALS:
        delta = (d - today).days
        if 0 <= delta <= within_days and delta < soonest_delta:
            soonest = (name, delta, occ, hint)
            soonest_delta = delta
    if soonest:
        return soonest
    return None, None, None, None

def festival_greeting_line(within_days: int = 21) -> str | None:
    """One sentence Mira can weave into her greeting about an upcoming festival."""
    name, delta, occ, hint = upcoming_festival(within_days)
    if name is None:
        return None
    if delta == 0:
        return f"Happy {name}! I've got some beautiful {hint} ideas ready for you."
    if delta <= 3:
        return f"{name} is in just {delta} days — want me to put together a {hint} look?"
    if delta <= 7:
        return f"{name} is this week — I can help you nail the {hint} look."
    return f"{name} is {delta} days away — perfect time to plan your {hint} outfit."
