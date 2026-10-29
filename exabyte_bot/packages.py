"""Plans are DATA. Edit the constants below to change prices or durations.

`category` lets other digital products be added later without changing code paths.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---- Easy-to-edit constants -------------------------------------------------
MONTHLY_PRICE_MMK = 5_000
DAYS_PER_MONTH = 30

TRIAL_QUOTA_GB = 5
TRIAL_DAYS = 7
TRIAL_COOLDOWN_DAYS = 7  # a new trial may be claimed this long after the previous claim

PAID_DEVICES = 1
REGENERATE_COOLDOWN_HOURS = 24
ORDER_EXPIRY_HOURS = 24
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    id: str
    category: str
    name: str  # Burmese display name
    months: int
    days: int
    discount_mmk: int = 0
    quota_gb: int | None = None  # None = unlimited
    devices: int = PAID_DEVICES
    badge: str | None = None  # strings.py key, or None
    description: str = ""
    best_value: bool = False
    multi_server: bool = False  # True = GB plan (can switch servers & shares GB across servers)

    @property
    def original_price_mmk(self) -> int:
        return self.months * MONTHLY_PRICE_MMK

    @property
    def price_mmk(self) -> int:
        return self.original_price_mmk - self.discount_mmk

    @property
    def unlimited(self) -> bool:
        return self.quota_gb is None

    @property
    def quota_bytes(self) -> int:
        return 0 if self.quota_gb is None else self.quota_gb * 1024**3


PLANS: tuple[Plan, ...] = (
    # --- Unlimited Data Plans (1 Device limit, locked to 1 chosen Server) ---
    Plan(id="vpn_1m", category="vpn", name="1 လ (Unlimited)", months=1, days=1 * DAYS_PER_MONTH),
    Plan(
        id="vpn_3m", category="vpn", name="3 လ (Unlimited)", months=3, days=3 * DAYS_PER_MONTH,
        discount_mmk=500, badge="badge_save",
    ),
    Plan(
        id="vpn_6m", category="vpn", name="6 လ (Unlimited)", months=6, days=6 * DAYS_PER_MONTH,
        discount_mmk=1_000, badge="badge_best", best_value=True,
    ),
    # --- Shared GB Data Plans (Multi-Server switching, shared GB balance across servers) ---
    Plan(
        id="vpn_gb_1m", category="vpn_gb", name="1 လ (100 GB)", months=1,
        days=1 * DAYS_PER_MONTH, quota_gb=100, multi_server=True,
    ),
    Plan(
        id="vpn_gb_3m", category="vpn_gb", name="3 လ (300 GB)", months=3,
        days=3 * DAYS_PER_MONTH, quota_gb=300, discount_mmk=500, badge="badge_save",
        multi_server=True,
    ),
    Plan(
        id="vpn_gb_6m", category="vpn_gb", name="6 လ (600 GB)", months=6,
        days=6 * DAYS_PER_MONTH, quota_gb=600, discount_mmk=1_000, badge="badge_best",
        best_value=True, multi_server=True,
    ),
)

_BY_ID = {p.id: p for p in PLANS}


def get_plan(plan_id: str) -> Plan | None:
    return _BY_ID.get(plan_id)


def plans_in(category: str) -> list[Plan]:
    return [p for p in PLANS if p.category == category]


def all_plans() -> list[Plan]:
    return list(PLANS)

