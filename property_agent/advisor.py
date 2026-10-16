"""Eligibility checks and segment recommendations.

Segments:
  HDB_RESALE, EC_NEW_LAUNCH, PRIVATE_RESALE, PRIVATE_NEW_LAUNCH, LANDED
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules
from .calculator import (
    Affordability, available_funds, max_affordable_price, monthly_instalment,
)
from .profile import ClientProfile

SEGMENT_LABELS = {
    "HDB_RESALE": "HDB Resale",
    "EC_NEW_LAUNCH": "New Launch EC",
    "PRIVATE_RESALE": "Resale Private Condo",
    "PRIVATE_NEW_LAUNCH": "New Launch Private Condo",
    "LANDED": "Landed",
}

# Eligibility status values
ELIGIBLE, CONDITIONAL, NOT_ELIGIBLE = "eligible", "conditional", "not_eligible"


@dataclass
class Eligibility:
    status: str = ELIGIBLE
    reasons: list[str] = field(default_factory=list)   # why not / conditions
    notes: list[str] = field(default_factory=list)     # useful context

    def block(self, reason: str):
        self.status = NOT_ELIGIBLE
        self.reasons.append(reason)

    def condition(self, reason: str):
        if self.status != NOT_ELIGIBLE:
            self.status = CONDITIONAL
        self.reasons.append(reason)


def _mop_check(p: ClientProfile, e: Eligibility):
    """HDB/EC owners must finish the 5-year MOP before selling or buying private."""
    cp = p.current_property
    if cp and cp.type in ("HDB", "EC") and cp.years_owned < rules.HDB_MOP_YEARS:
        wait = rules.HDB_MOP_YEARS - cp.years_owned
        e.condition(f"Current {cp.type} has not met the {rules.HDB_MOP_YEARS}-year MOP "
                    f"(~{wait:.1f} more years) - cannot sell it or buy private until then.")


def check_hdb_resale(p: ClientProfile) -> Eligibility:
    e = Eligibility()
    if not p.has_citizen:
        if p.residency == "PR" and p.co_applicant_residency == "PR" and p.is_family:
            e.condition("PR households need both owners to have held PR for at least 3 years; "
                        "no CPF housing grants for PR-PR households.")
        else:
            e.block("HDB flats need at least one Singapore Citizen buyer "
                    "(or a PR-PR family nucleus). Foreigners and single PRs cannot buy HDB.")
    if p.has_citizen and not p.is_family and p.age < rules.HDB_SINGLE_MIN_AGE:
        e.block(f"Singles must be at least {rules.HDB_SINGLE_MIN_AGE} to buy an HDB resale flat.")
    if p.purpose == "investment":
        e.block("HDB flats must be owner-occupied; not suitable as an investment purchase.")
    if p.keeps_current:
        e.block("Cannot keep the current property and buy an HDB flat - "
                "HDB buyers may own only one HDB and no private property.")
    if p.owns_private_now and not p.sells_current:
        e.block("Owners of private property must dispose of it before buying HDB.")
    cp = p.current_property
    if cp and cp.type in ("PRIVATE", "LANDED") and cp.plan == "sell":
        e.condition(f"After selling private property there is a {rules.PRIVATE_TO_HDB_WAIT_MONTHS}-month "
                    "wait-out before buying a resale HDB (seniors 55+ buying a 4-room or smaller are exempt).")
    if p.years_since_disposed_private is not None and p.years_since_disposed_private * 12 < rules.PRIVATE_TO_HDB_WAIT_MONTHS:
        e.condition(f"Private property disposed less than {rules.PRIVATE_TO_HDB_WAIT_MONTHS} months ago - wait-out applies.")
    if cp and cp.type in ("HDB", "EC"):
        _mop_check(p, e)
    if p.has_citizen and p.monthly_income <= rules.HDB_LOAN_INCOME_CEILING:
        e.notes.append("May qualify for CPF Housing Grants (Enhanced/Family/Proximity) - check HDB eligibility letter.")
    return e


def check_ec_new_launch(p: ClientProfile) -> Eligibility:
    e = Eligibility()
    if not p.has_citizen:
        e.block("New ECs require at least one Singapore Citizen buyer.")
    elif not p.is_family:
        e.block("Singles cannot buy new-launch ECs (only resale ECs after 10 years).")
    elif "FOREIGNER" in p.buyers:
        e.block("New EC co-applicants must be Singapore Citizens or PRs.")
    if p.monthly_income > rules.EC_INCOME_CEILING:
        e.block(f"Household income ${p.monthly_income:,.0f} exceeds the EC ceiling of "
                f"${rules.EC_INCOME_CEILING:,}/month.")
    if p.purpose == "investment":
        e.block("ECs carry a 5-year MOP with owner-occupation; not suitable as an investment purchase.")
    if p.owns_private_now:
        e.block(f"Must not own private property, or have disposed of it in the last "
                f"{rules.PRIVATE_TO_EC_WAIT_MONTHS} months, to buy a new EC.")
    elif p.years_since_disposed_private is not None and p.years_since_disposed_private * 12 < rules.PRIVATE_TO_EC_WAIT_MONTHS:
        e.block(f"Private property disposed less than {rules.PRIVATE_TO_EC_WAIT_MONTHS} months ago.")
    cp = p.current_property
    if cp and cp.type in ("HDB", "EC"):
        _mop_check(p, e)
        e.condition(f"Must sell the current {cp.type} within 6 months of collecting the EC keys; "
                    "ABSD is paid upfront and refunded on disposal (married SC couples).")
        e.notes.append("Can keep living in the current flat during the ~3-4 years of EC construction.")
    if p.has_citizen and p.monthly_income <= 12_000:
        e.notes.append("Income at or below $12,000 may qualify for the CPF Housing Grant for ECs.")
    return e


def _private_common(p: ClientProfile, e: Eligibility):
    cp = p.current_property
    if cp and cp.type in ("HDB", "EC"):
        _mop_check(p, e)
    if p.absd_residency == "FOREIGNER":
        e.notes.append("Foreigners pay 60% ABSD (US, Swiss, Norwegian, Icelandic and Liechtenstein "
                       "nationals may get SC treatment under FTAs - verify with IRAS).")
    if p.keeps_current and p.properties_after_purchase >= 2:
        e.notes.append("Buying while keeping the current home attracts second-property ABSD and a lower LTV.")


def check_private_resale(p: ClientProfile) -> Eligibility:
    e = Eligibility()
    _private_common(p, e)
    return e


def check_private_new_launch(p: ClientProfile) -> Eligibility:
    e = Eligibility()
    _private_common(p, e)
    e.notes.append("Progressive payment scheme: loan drawn down in stages during construction (~3-4 years to TOP).")
    if (p.sells_current and p.household_type == "married_couple" and p.has_citizen):
        e.notes.append("Married SC couples can buy first and claim back second-property ABSD "
                       "if they sell the current home within 6 months of TOP.")
    return e


def check_landed(p: ClientProfile) -> Eligibility:
    e = Eligibility()
    if "FOREIGNER" in p.buyers:
        e.block("Foreigners cannot buy landed homes on the mainland (Sentosa Cove only, with SLA approval).")
    elif "PR" in p.buyers and not p.has_citizen:
        e.condition("PRs need Land Dealings Approval Unit (SLA) approval to buy landed - "
                    "typically one property for own occupation, subject to strict criteria.")
    cp = p.current_property
    if cp and cp.type in ("HDB", "EC"):
        _mop_check(p, e)
    return e


CHECKS = {
    "HDB_RESALE": check_hdb_resale,
    "EC_NEW_LAUNCH": check_ec_new_launch,
    "PRIVATE_RESALE": check_private_resale,
    "PRIVATE_NEW_LAUNCH": check_private_new_launch,
    "LANDED": check_landed,
}


def _affordability_status(aff: Affordability, band: dict) -> str:
    if aff.max_price >= band["typical"]:
        return "comfortable"
    if aff.max_price >= band["entry"]:
        return "stretch"
    return "out_of_reach"


def _score(p: ClientProfile, segment: str, elig: Eligibility, status: str, aff: Affordability) -> tuple[int, list[str]]:
    if elig.status == NOT_ELIGIBLE:
        return 0, ["Not eligible"]
    score, why = 50, []
    score += {"comfortable": 30, "stretch": 5, "out_of_reach": -40}[status]
    why.append(f"Affordability: {status.replace('_', ' ')}")
    if elig.status == CONDITIONAL:
        score -= 10
        why.append("Has conditions to satisfy first")
    if aff.absd_rate > 0:
        penalty = int(aff.absd_rate * 60)
        score -= penalty
        why.append(f"ABSD {aff.absd_rate:.0%} adds significant upfront cost")

    new_launch = segment in ("EC_NEW_LAUNCH", "PRIVATE_NEW_LAUNCH")
    if new_launch and p.timeline == "immediate":
        score -= 15
        why.append("New launch takes ~3-4 years to complete; client needs to move soon")
    if not new_launch and p.timeline == "immediate":
        score += 5
        why.append("Ready to move in")
    if new_launch and p.timeline == "flexible":
        score += 5
        why.append("Progressive payments ease cash flow while waiting for TOP")
    if segment == "EC_NEW_LAUNCH" and elig.status != NOT_ELIGIBLE:
        score += 10
        why.append("EC offers condo living below private prices, privatises after 10 years")
    if segment == "HDB_RESALE" and p.monthly_income <= rules.HDB_LOAN_INCOME_CEILING and p.has_citizen:
        score += 5
        why.append("Grants / HDB loan may apply")
    if p.purpose == "investment" and segment in ("PRIVATE_RESALE", "PRIVATE_NEW_LAUNCH"):
        score += 10
        why.append("Can be rented out without occupancy restrictions")
    if segment == "LANDED" and status == "comfortable":
        score += 5
        why.append("Land value tends to hold well; scarce supply")
    return max(0, min(100, score)), why


def analyse(p: ClientProfile) -> dict:
    """Run the full analysis and return a JSON-serialisable report."""
    funds = available_funds(p)
    results = []
    for segment, check in CHECKS.items():
        elig = check(p)
        band = rules.PRICE_BANDS[segment]
        aff = max_affordable_price(p, segment, funds)
        status = _affordability_status(aff, band)
        score, why = _score(p, segment, elig, status, aff)
        target = min(aff.max_price, band["typical"])
        loan_at_target = min(target * aff.ltv, aff.max_loan_by_income)
        results.append({
            "segment": segment,
            "label": SEGMENT_LABELS[segment],
            "eligibility": elig.status,
            "eligibility_reasons": elig.reasons,
            "notes": elig.notes,
            "price_band": band,
            "max_affordable_price": aff.to_dict(),
            "affordability": status if elig.status != NOT_ELIGIBLE else "n/a",
            "illustrative_purchase": {
                "price": round(target),
                "loan": round(loan_at_target),
                "monthly_instalment": round(monthly_instalment(loan_at_target, rules.ASSUMED_MARKET_RATE, aff.tenure_years)),
                "assumed_rate": rules.ASSUMED_MARKET_RATE,
            } if elig.status != NOT_ELIGIBLE and status != "out_of_reach" else None,
            "suitability_score": score,
            "score_factors": why,
        })
    results.sort(key=lambda r: r["suitability_score"], reverse=True)
    viable = [r for r in results if r["eligibility"] != NOT_ELIGIBLE and r["affordability"] != "out_of_reach"]
    return {
        "policy_as_of": rules.POLICY_AS_OF,
        "client_summary": {
            "buyers": p.buyers,
            "household_type": p.household_type,
            "absd_treated_as": p.absd_residency,
            "property_count_after_purchase": p.properties_after_purchase,
            "housing_loans_after_purchase": p.housing_loans_after_purchase,
            "monthly_income": p.monthly_income,
            "funds_available": funds.to_dict(),
        },
        "top_recommendation": viable[0]["label"] if viable else None,
        "ranked_options": results,
        "disclaimer": ("Indicative analysis using simplified rules and assumed prices. Confirm eligibility "
                       "with HDB, stamp duties with IRAS, and loan amounts with a bank In-Principle Approval."),
    }


def format_report(report: dict) -> str:
    """Plain-text rendering for the offline CLI."""
    s = report["client_summary"]
    f = s["funds_available"]
    lines = [
        "=" * 64,
        "PROPERTY OPTIONS ANALYSIS",
        "=" * 64,
        f"Buyers: {', '.join(s['buyers'])} ({s['household_type'].replace('_', ' ')}) | "
        f"ABSD profile: {s['absd_treated_as']} | property #{s['property_count_after_purchase']}",
        f"Household income: ${s['monthly_income']:,.0f}/month",
        f"Funds: CPF OA ${f['cpf']:,} | Cash ${f['cash']:,}"
        + (f"  (incl. sale proceeds ${f['sale_cash_proceeds']:,} cash, ${f['cpf_refund_from_sale']:,} CPF refund)"
           if f["sale_cash_proceeds"] or f["cpf_refund_from_sale"] else ""),
        "",
        f"Top recommendation: {report['top_recommendation'] or 'None currently viable - see notes'}",
        "",
    ]
    for i, r in enumerate(report["ranked_options"], 1):
        a = r["max_affordable_price"]
        lines.append(f"{i}. {r['label']:<26} score {r['suitability_score']:>3}/100  "
                     f"[{r['eligibility'].replace('_', ' ')} | {r['affordability'].replace('_', ' ')}]")
        if r["eligibility"] != NOT_ELIGIBLE:
            lines.append(f"   Max price ~${a['max_price']:,} ({a['financing'].replace('_', ' ')}, "
                         f"LTV {a['ltv']:.0%}, {a['tenure_years']}y; limited by {a['binding_constraint']})")
            lines.append(f"   Market: {r['price_band']['note']}")
            ip = r["illustrative_purchase"]
            if ip:
                lines.append(f"   e.g. ${ip['price']:,} -> loan ${ip['loan']:,}, "
                             f"~${ip['monthly_instalment']:,}/month at {ip['assumed_rate']:.1%}")
            if a["absd"]:
                lines.append(f"   Stamp duty at max price: BSD ${a['bsd']:,} + ABSD ${a['absd']:,} ({a['absd_rate']:.0%})")
        for reason in r["eligibility_reasons"]:
            lines.append(f"   ! {reason}")
        for note in r["notes"]:
            lines.append(f"   - {note}")
        lines.append("")
    lines.append(report["disclaimer"])
    return "\n".join(lines)
