"""Client profile data model."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

RESIDENCIES = ("SC", "PR", "FOREIGNER")
HOUSEHOLD_TYPES = ("single", "married_couple", "other_joint")
PROPERTY_TYPES = ("HDB", "EC", "PRIVATE", "LANDED")
PLANS = ("sell", "keep")
PURPOSES = ("own_stay", "investment")
TIMELINES = ("immediate", "flexible")

_RESIDENCY_ALIASES = {
    "SINGAPOREAN": "SC", "CITIZEN": "SC", "SG": "SC", "SINGAPORE CITIZEN": "SC",
    "PERMANENT RESIDENT": "PR", "SPR": "PR",
    "FOREIGN": "FOREIGNER", "NON-RESIDENT": "FOREIGNER", "OTHER": "FOREIGNER",
}


class ProfileError(ValueError):
    """Raised when client input is missing or invalid."""


def _residency(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper()
    v = _RESIDENCY_ALIASES.get(v, v)
    if v not in RESIDENCIES:
        raise ProfileError(f"{field_name} must be one of {RESIDENCIES}, got {value!r}")
    return v


def _choice(value, options, field_name, default=None):
    if value is None:
        return default
    v = str(value).strip().lower()
    if v not in options:
        raise ProfileError(f"{field_name} must be one of {options}, got {value!r}")
    return v


def _money(value, field_name, default=0.0) -> float:
    if value is None:
        return default
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ProfileError(f"{field_name} must be a number, got {value!r}") from None
    if v < 0:
        raise ProfileError(f"{field_name} cannot be negative")
    return v


@dataclass
class CurrentProperty:
    type: str                         # HDB | EC | PRIVATE | LANDED
    estimated_value: float
    outstanding_loan: float = 0.0
    cpf_used_with_interest: float = 0.0   # refunded to CPF OA on sale
    years_owned: float = 0.0
    plan: str = "sell"                # sell | keep

    @classmethod
    def from_dict(cls, d: dict) -> "CurrentProperty":
        ptype = str(d.get("type", "")).strip().upper()
        if ptype not in PROPERTY_TYPES:
            raise ProfileError(f"current_property.type must be one of {PROPERTY_TYPES}, got {d.get('type')!r}")
        return cls(
            type=ptype,
            estimated_value=_money(d.get("estimated_value"), "current_property.estimated_value"),
            outstanding_loan=_money(d.get("outstanding_loan"), "current_property.outstanding_loan"),
            cpf_used_with_interest=_money(d.get("cpf_used_with_interest"), "current_property.cpf_used_with_interest"),
            years_owned=_money(d.get("years_owned"), "current_property.years_owned"),
            plan=_choice(d.get("plan"), PLANS, "current_property.plan", "sell"),
        )


@dataclass
class ClientProfile:
    residency: str                          # main buyer: SC | PR | FOREIGNER
    age: int
    monthly_income: float                   # gross household income of all buyers
    cpf_oa_balance: float = 0.0             # combined CPF Ordinary Account
    cash_savings: float = 0.0               # cash available for the purchase
    household_type: str = "single"
    co_applicant_residency: Optional[str] = None
    existing_monthly_debt: float = 0.0      # car loans, other mortgages, etc.
    current_property: Optional[CurrentProperty] = None
    other_properties_count: int = 0         # properties owned besides current_property
    purpose: str = "own_stay"
    timeline: str = "flexible"
    years_since_disposed_private: Optional[float] = None  # if they sold a private home recently

    @classmethod
    def from_dict(cls, d: dict) -> "ClientProfile":
        if not isinstance(d, dict):
            raise ProfileError("profile must be an object")
        for key in ("residency", "age", "monthly_income"):
            if d.get(key) is None:
                raise ProfileError(f"missing required field: {key}")
        age = int(_money(d.get("age"), "age"))
        if not 21 <= age <= 99:
            raise ProfileError("age must be between 21 and 99")
        cp = d.get("current_property")
        household = _choice(d.get("household_type"), HOUSEHOLD_TYPES, "household_type", "single")
        co_res = _residency(d.get("co_applicant_residency"), "co_applicant_residency")
        if household == "single" and co_res:
            household = "other_joint"
        return cls(
            residency=_residency(d.get("residency"), "residency"),
            age=age,
            monthly_income=_money(d.get("monthly_income"), "monthly_income"),
            cpf_oa_balance=_money(d.get("cpf_oa_balance"), "cpf_oa_balance"),
            cash_savings=_money(d.get("cash_savings"), "cash_savings"),
            household_type=household,
            co_applicant_residency=co_res,
            existing_monthly_debt=_money(d.get("existing_monthly_debt"), "existing_monthly_debt"),
            current_property=CurrentProperty.from_dict(cp) if cp else None,
            other_properties_count=int(_money(d.get("other_properties_count"), "other_properties_count")),
            purpose=_choice(d.get("purpose"), PURPOSES, "purpose", "own_stay"),
            timeline=_choice(d.get("timeline"), TIMELINES, "timeline", "flexible"),
            years_since_disposed_private=(
                None if d.get("years_since_disposed_private") is None
                else _money(d.get("years_since_disposed_private"), "years_since_disposed_private")
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    # --- derived facts ---------------------------------------------------
    @property
    def buyers(self) -> list[str]:
        return [r for r in (self.residency, self.co_applicant_residency) if r]

    @property
    def has_citizen(self) -> bool:
        return "SC" in self.buyers

    @property
    def is_family(self) -> bool:
        return self.household_type in ("married_couple", "other_joint") and len(self.buyers) >= 2

    @property
    def keeps_current(self) -> bool:
        return self.current_property is not None and self.current_property.plan == "keep"

    @property
    def sells_current(self) -> bool:
        return self.current_property is not None and self.current_property.plan == "sell"

    @property
    def owns_private_now(self) -> bool:
        cp = self.current_property
        return (cp is not None and cp.type in ("PRIVATE", "LANDED")) or self.other_properties_count > 0

    @property
    def absd_residency(self) -> str:
        """Residency profile used for ABSD.

        Joint purchases pay the highest applicable rate, except married couples
        with at least one Singapore Citizen, who are generally remitted to SC rates.
        """
        if self.household_type == "married_couple" and self.has_citizen:
            return "SC"
        order = {"SC": 0, "PR": 1, "FOREIGNER": 2}
        return max(self.buyers, key=order.__getitem__)

    @property
    def properties_after_purchase(self) -> int:
        held = self.other_properties_count + (1 if self.keeps_current else 0)
        return min(held + 1, 3)

    @property
    def housing_loans_after_purchase(self) -> int:
        """Outstanding housing loans including the new one (drives LTV tier)."""
        existing = 0
        if self.keeps_current and self.current_property.outstanding_loan > 0:
            existing += 1
        return min(existing + 1, 3)
