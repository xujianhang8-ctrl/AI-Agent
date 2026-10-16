import json
from types import SimpleNamespace

import pytest

from property_agent import ClientProfile, ProfileError, analyse
from property_agent.agent import PropertyAdvisorAgent, run_tool
from property_agent.calculator import buyer_stamp_duty, stamp_duty_breakdown


def by_segment(report):
    return {r["segment"]: r for r in report["ranked_options"]}


def profile(**kw):
    base = {"residency": "SC", "age": 35, "monthly_income": 12000,
            "cpf_oa_balance": 150000, "cash_savings": 100000}
    base.update(kw)
    return ClientProfile.from_dict(base)


def test_bsd_tiers():
    # 1% of 180k + 2% of 180k + 3% of 640k = 1,800 + 3,600 + 19,200
    assert buyer_stamp_duty(1_000_000) == 24_600
    assert buyer_stamp_duty(180_000) == 1_800


def test_absd_rates():
    assert stamp_duty_breakdown(1_000_000, "SC", 1)["absd"] == 0
    assert stamp_duty_breakdown(1_000_000, "SC", 2)["absd"] == 200_000
    assert stamp_duty_breakdown(1_000_000, "PR", 1)["absd"] == 50_000
    assert stamp_duty_breakdown(1_000_000, "FOREIGNER", 1)["absd"] == 600_000


def test_foreigner_only_private_non_landed():
    seg = by_segment(analyse(profile(residency="FOREIGNER", cash_savings=2_000_000, monthly_income=30000)))
    assert seg["HDB_RESALE"]["eligibility"] == "not_eligible"
    assert seg["EC_NEW_LAUNCH"]["eligibility"] == "not_eligible"
    assert seg["LANDED"]["eligibility"] == "not_eligible"
    assert seg["PRIVATE_RESALE"]["eligibility"] == "eligible"
    assert seg["PRIVATE_RESALE"]["max_affordable_price"]["absd_rate"] == 0.60


def test_ec_income_ceiling_and_singles():
    seg = by_segment(analyse(profile(co_applicant_residency="SC", household_type="married_couple",
                                     monthly_income=18000)))
    assert seg["EC_NEW_LAUNCH"]["eligibility"] == "not_eligible"
    seg = by_segment(analyse(profile()))
    assert seg["EC_NEW_LAUNCH"]["eligibility"] == "not_eligible"  # single


def test_private_owner_cannot_buy_ec_or_keep_and_buy_hdb():
    p = profile(co_applicant_residency="SC", household_type="married_couple",
                current_property={"type": "PRIVATE", "estimated_value": 1_200_000, "plan": "keep"})
    seg = by_segment(analyse(p))
    assert seg["EC_NEW_LAUNCH"]["eligibility"] == "not_eligible"
    assert seg["HDB_RESALE"]["eligibility"] == "not_eligible"
    assert p.properties_after_purchase == 2
    assert seg["PRIVATE_RESALE"]["max_affordable_price"]["absd_rate"] == 0.20


def test_hdb_mop_not_met_is_conditional():
    p = profile(current_property={"type": "HDB", "estimated_value": 600000, "years_owned": 3, "plan": "sell"})
    seg = by_segment(analyse(p))
    assert seg["PRIVATE_RESALE"]["eligibility"] == "conditional"
    assert any("MOP" in r for r in seg["PRIVATE_RESALE"]["eligibility_reasons"])


def test_selling_adds_proceeds_and_cpf_refund():
    p = profile(cash_savings=0, cpf_oa_balance=0,
                current_property={"type": "HDB", "estimated_value": 600000, "outstanding_loan": 100000,
                                  "cpf_used_with_interest": 200000, "years_owned": 8, "plan": "sell"})
    funds = analyse(p)["client_summary"]["funds_available"]
    assert funds["cpf"] == 200000
    assert funds["cash"] == 600000 * 0.98 - 100000 - 200000


def test_higher_income_raises_budget():
    low = by_segment(analyse(profile(monthly_income=6000, cash_savings=1_000_000)))
    high = by_segment(analyse(profile(monthly_income=20000, cash_savings=1_000_000)))
    assert (high["PRIVATE_RESALE"]["max_affordable_price"]["max_price"]
            > low["PRIVATE_RESALE"]["max_affordable_price"]["max_price"])


def test_married_sc_foreigner_gets_sc_absd():
    p = profile(co_applicant_residency="FOREIGNER", household_type="married_couple")
    assert p.absd_residency == "SC"
    p = profile(co_applicant_residency="FOREIGNER", household_type="other_joint")
    assert p.absd_residency == "FOREIGNER"


def test_invalid_profile():
    with pytest.raises(ProfileError):
        ClientProfile.from_dict({"residency": "martian", "age": 30, "monthly_income": 1})
    out, is_error = run_tool("analyze_property_options", {"age": 30})
    assert is_error and "residency" in out


# --- agent loop with a fake Claude client ---------------------------------

class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _resp(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def test_agent_runs_tool_and_returns_text():
    tool_input = {"residency": "SC", "age": 35, "monthly_income": 12000,
                  "cpf_oa_balance": 100000, "cash_savings": 80000}
    fake = FakeMessages([
        _resp("tool_use", SimpleNamespace(type="tool_use", id="t1", name="analyze_property_options", input=tool_input)),
        _resp("end_turn", SimpleNamespace(type="text", text="I'd suggest a resale condo.")),
    ])
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    agent = PropertyAdvisorAgent(client=client)
    assert agent.send("Here are my details") == "I'd suggest a resale condo."
    tool_result = agent.messages[2]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and not tool_result["is_error"]
    assert "ranked_options" in json.loads(tool_result["content"])
    assert fake.calls[0]["model"] == "claude-opus-5-5"
