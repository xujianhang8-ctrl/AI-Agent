# Singapore Property Advisor Agent

An AI assistant for property agents. It helps clients choose their next move:
**HDB Resale, New Launch EC, Resale Private, New Launch Private, or Landed**. It bases the
recommendation on residency, household, income, CPF, cash and any property the client already owns.

It has two layers:

1. **Rules engine** (`property_agent/advisor.py`, `calculator.py`, `rules.py`). This is plain Python
   and gives the same answer for the same inputs. It checks eligibility (citizenship, EC income
   ceiling, MOP, private-property wait-outs, landed restrictions). It also works out how much the
   client can borrow (TDSR, MSR, LTV, loan tenure), BSD and ABSD, and net sale proceeds with the
   CPF refund. Then it ranks each segment with a suitability score and lists the reasons.
2. **Claude agent** (`property_agent/agent.py`). This chats with the client to collect the details,
   then calls the rules engine as a tool and explains the result in plain language. All figures
   come from the engine, not from the model's memory.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # only needed for chat mode
```

## Usage

```bash
# Conversational agent (Claude)
python -m property_agent chat

# Offline questionnaire, no API key needed
python -m property_agent quick

# Analyse a saved client profile
python -m property_agent analyze examples/hdb_upgrader.json
python -m property_agent analyze examples/foreigner.json --json
```

Use it from your own code (e.g. a WhatsApp/Telegram bot or a web form):

```python
from property_agent import ClientProfile, analyse
from property_agent.agent import PropertyAdvisorAgent

report = analyse(ClientProfile.from_dict({...}))      # structured dict
agent = PropertyAdvisorAgent()
print(agent.send("Hi, we're an SC couple earning 12k, own a 4-room HDB..."))
```

## Client profile fields

| Field | Example | Notes |
|---|---|---|
| `residency` | `SC` / `PR` / `FOREIGNER` | main buyer |
| `co_applicant_residency` | `PR` | optional |
| `household_type` | `single` / `married_couple` / `other_joint` | married couples with an SC get SC ABSD rates |
| `age` | `35` | sets the loan tenure |
| `monthly_income` | `14500` | gross household income |
| `existing_monthly_debt` | `800` | car loan, other mortgages |
| `cpf_oa_balance`, `cash_savings` | `120000`, `80000` | |
| `current_property` | `{type, estimated_value, outstanding_loan, cpf_used_with_interest, years_owned, plan}` | `plan` is `sell` or `keep` |
| `other_properties_count` | `0` | |
| `purpose` | `own_stay` / `investment` | |
| `timeline` | `immediate` / `flexible` | new launches are penalised if the client must move soon |

## Keep the rules current

Every policy number and price band is in **`property_agent/rules.py`**: ABSD, BSD tiers, TDSR/MSR,
stress rate, LTV, EC income ceiling, MOP, wait-out periods and indicative 2026 prices. Singapore
cooling measures change often. Check that file against IRAS, HDB, MAS and CPF before using it with
clients, and update the price bands with your own transaction data.

Simplifications to know about: the engine does not model CPF housing grants, CPF usage limits on
older leases, Valuation Limits, bridging loans, or the cash flow of buying first and selling later.
These are listed as notes or should be checked manually.

## Model

The agent uses `claude-opus-5-5` with adaptive thinking at `medium` effort. Server-side refusal
fallback is turned on (`fallbacks="default"`). Change `MODEL` in `agent.py` to use a different model.

## Tests

```bash
python -m pytest -q
```

> Indicative analysis only. It is not financial or legal advice. Confirm eligibility with HDB,
> stamp duties with IRAS, and loan amounts with a bank In-Principle Approval.

## Web chatbot (no install)

`web/property-advisor.html` is a standalone chatbot page with the same rules engine rewritten in
JavaScript. Published as a Claude artifact, it chats through the viewer's own Claude account, so it
needs no API key. Its **Quick check** tab runs the calculator directly with no AI at all.
