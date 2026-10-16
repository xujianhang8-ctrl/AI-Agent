"""Stamp duty, loan capacity and maximum-price calculations."""

from __future__ import annotations

from dataclasses import dataclass, asdict

from . import rules
from .profile import ClientProfile


def buyer_stamp_duty(price: float) -> float:
    duty, remaining = 0.0, price
    for size, rate in rules.BSD_TIERS:
        portion = min(remaining, size)
        duty += portion * rate
        remaining -= portion
        if remaining <= 0:
            break
    return round(duty, 2)


def absd_rate(residency: str, property_count_after_purchase: int) -> float:
    return rules.ABSD_RATES[residency][min(max(property_count_after_purchase, 1), 3)]


def additional_buyer_stamp_duty(price: float, residency: str, property_count_after_purchase: int) -> float:
    return round(price * absd_rate(residency, property_count_after_purchase), 2)


def monthly_instalment(loan: float, annual_rate: float, years: int) -> float:
    if loan <= 0 or years <= 0:
        return 0.0
    r, n = annual_rate / 12, years * 12
    if r == 0:
        return loan / n
    return loan * r / (1 - (1 + r) ** -n)


def loan_from_instalment(instalment: float, annual_rate: float, years: int) -> float:
    if instalment <= 0 or years <= 0:
        return 0.0
    r, n = annual_rate / 12, years * 12
    if r == 0:
        return instalment * n
    return instalment * (1 - (1 + r) ** -n) / r


@dataclass
class Funds:
    cpf: float
    cash: float
    sale_cash_proceeds: float
    cpf_refund_from_sale: float

    def to_dict(self):
        return {k: round(v) for k, v in asdict(self).items()}


def available_funds(p: ClientProfile) -> Funds:
    cpf, cash = p.cpf_oa_balance, p.cash_savings
    proceeds = refund = 0.0
    cp = p.current_property
    if cp is not None and cp.plan == "sell":
        refund = cp.cpf_used_with_interest
        gross = cp.estimated_value * (1 - rules.SELLING_COST_PCT) - cp.outstanding_loan
        proceeds = max(gross - refund, 0.0)
        # If the sale can't cover the full CPF refund, only what's left goes back.
        refund = min(refund, max(gross, 0.0))
    return Funds(cpf=cpf + refund, cash=cash + proceeds,
                 sale_cash_proceeds=proceeds, cpf_refund_from_sale=refund)


@dataclass
class Financing:
    name: str                 # "bank" | "hdb_loan"
    ltv: float
    min_cash_pct: float
    tenure: int
    stress_rate: float
    apply_msr: bool


def financing_options(p: ClientProfile, segment: str) -> list[Financing]:
    loans = p.housing_loans_after_purchase
    is_hdb = segment == "HDB_RESALE"
    msr = segment in ("HDB_RESALE", "EC_NEW_LAUNCH")
    bank_max = rules.MAX_TENURE_BANK_HDB if is_hdb else rules.MAX_TENURE_BANK_PRIVATE
    tenure = max(5, min(bank_max, rules.LOAN_END_AGE - p.age))
    options = [Financing("bank", rules.BANK_LTV[loans], rules.BANK_MIN_CASH_PCT[loans],
                         tenure, rules.STRESS_RATE_BANK, msr)]
    if is_hdb and hdb_loan_eligible(p):
        options.append(Financing(
            "hdb_loan", rules.HDB_LOAN_LTV, rules.HDB_LOAN_MIN_CASH_PCT,
            max(5, min(rules.MAX_TENURE_HDB_LOAN, rules.LOAN_END_AGE - p.age)),
            rules.HDB_LOAN_RATE, True))
    return options


def hdb_loan_eligible(p: ClientProfile) -> bool:
    ceiling = rules.HDB_LOAN_INCOME_CEILING if p.is_family else rules.HDB_LOAN_INCOME_CEILING_SINGLE
    return p.has_citizen and p.monthly_income <= ceiling and not p.owns_private_now


def max_loan_by_income(p: ClientProfile, f: Financing) -> float:
    tdsr_room = p.monthly_income * rules.TDSR_LIMIT - p.existing_monthly_debt
    room = tdsr_room
    if f.apply_msr:
        room = min(room, p.monthly_income * rules.MSR_LIMIT)
    return loan_from_instalment(max(room, 0.0), f.stress_rate, f.tenure)


@dataclass
class Affordability:
    max_price: float
    financing: str
    loan_amount: float
    max_loan_by_income: float
    ltv: float
    tenure_years: int
    bsd: float
    absd: float
    absd_rate: float
    binding_constraint: str

    def to_dict(self):
        d = asdict(self)
        for k in ("max_price", "loan_amount", "max_loan_by_income", "bsd", "absd"):
            d[k] = round(d[k])
        return d


def _check(price: float, p: ClientProfile, f: Financing, funds: Funds, income_loan: float):
    """Return (ok, binding_constraint, details) for a candidate price."""
    loan = min(price * f.ltv, income_loan)
    bsd = buyer_stamp_duty(price)
    absd = additional_buyer_stamp_duty(price, p.absd_residency, p.properties_after_purchase)
    min_cash = price * f.min_cash_pct
    need_total = price - loan + bsd + absd + rules.LEGAL_AND_MISC_FEES
    if funds.cash < min_cash:
        return False, "minimum cash downpayment", (loan, bsd, absd)
    if funds.cash + funds.cpf < need_total:
        limiter = "loan limit (income / TDSR-MSR)" if loan < price * f.ltv else "downpayment + stamp duties (cash/CPF)"
        return False, limiter, (loan, bsd, absd)
    return True, "", (loan, bsd, absd)


def max_affordable_price(p: ClientProfile, segment: str, funds: Funds | None = None) -> Affordability:
    """Highest price the client can fund for a segment, across their financing options."""
    funds = funds or available_funds(p)
    best: Affordability | None = None
    for f in financing_options(p, segment):
        income_loan = max_loan_by_income(p, f)
        lo, hi = 0.0, 20_000_000.0
        constraint = "funds"
        for _ in range(60):
            mid = (lo + hi) / 2
            ok, why, _ = _check(mid, p, f, funds, income_loan)
            if ok:
                lo = mid
            else:
                hi, constraint = mid, why
        price = round(lo, -3)
        _, _, (loan, bsd, absd) = _check(price, p, f, funds, income_loan)
        result = Affordability(
            max_price=price, financing=f.name, loan_amount=loan,
            max_loan_by_income=income_loan, ltv=f.ltv, tenure_years=f.tenure,
            bsd=bsd, absd=absd, absd_rate=absd_rate(p.absd_residency, p.properties_after_purchase),
            binding_constraint=constraint,
        )
        if best is None or result.max_price > best.max_price:
            best = result
    return best


def stamp_duty_breakdown(price: float, residency: str, property_count_after_purchase: int) -> dict:
    bsd = buyer_stamp_duty(price)
    absd = additional_buyer_stamp_duty(price, residency, property_count_after_purchase)
    return {
        "price": round(price),
        "residency": residency,
        "property_count_after_purchase": property_count_after_purchase,
        "bsd": round(bsd),
        "absd_rate": absd_rate(residency, property_count_after_purchase),
        "absd": round(absd),
        "total_stamp_duty": round(bsd + absd),
        "policy_as_of": rules.POLICY_AS_OF,
    }
