"""Conversational property advisor powered by Claude.

Claude talks to the client, gathers their profile, and calls the local
rules engine (advisor.analyse) through tool use so every number it quotes
comes from deterministic calculations rather than the model's memory.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from typing import Callable

import anthropic

from .advisor import analyse
from .calculator import stamp_duty_breakdown
from .profile import ClientProfile, ProfileError

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """\
You are a friendly, professional assistant working for a Singapore property agent. \
You help clients figure out their next move: HDB resale, new-launch EC, resale private condo, \
new-launch private condo, or landed.

How to work:
1. Gather the client's details conversationally, a few questions at a time. You need:
   - Residency of the main buyer (Singapore Citizen / PR / foreigner) and any co-buyer, and whether they are a married couple
   - Age of the main buyer
   - Gross monthly household income, and existing monthly debt repayments (car loan, other mortgages)
   - Combined CPF Ordinary Account balance and cash savings available for the purchase
   - Whether they own a property now. If so: type (HDB / EC / private / landed), estimated value, outstanding loan, \
CPF used including accrued interest, years owned, and whether they plan to sell or keep it
   - Purpose (own stay or investment) and timeline (need to move soon, or flexible)
   If the client doesn't know a figure (e.g. CPF used incl. interest), suggest where to find it or use a reasonable \
estimate and say you did.
2. Once you have enough, call analyze_property_options. Re-run it whenever the client changes an assumption \
("what if we keep the HDB?").
3. Explain the result in plain language: the top 1-2 recommendations and why, a rough budget and monthly instalment, \
what's ruled out and why, and the key conditions (MOP, wait-out periods, ABSD, income ceilings). \
Use calculate_stamp_duty for specific prices the client mentions.

Rules:
- Every number you quote about eligibility, loans, budgets or stamp duty must come from the tools. \
Do not state policy figures from memory.
- Be clear that this is an indicative first-cut analysis; the agent will confirm with HDB, IRAS and a bank \
In-Principle Approval before any commitment.
- Keep replies concise and easy to read on a phone. Use S$ for amounts.
- If the client wants to proceed, view units, or has detailed questions about specific projects, offer to arrange \
a call with the agent. Ask for their name and phone number (and preferred contact time), then call save_lead with \
a short summary of their situation and your recommendation. Only call save_lead after the client has agreed to be contacted.
"""

_PROPERTY_SCHEMA = {
    "type": "object",
    "description": "The property the client currently owns, if any.",
    "properties": {
        "type": {"type": "string", "enum": ["HDB", "EC", "PRIVATE", "LANDED"]},
        "estimated_value": {"type": "number", "description": "Estimated market value in SGD"},
        "outstanding_loan": {"type": "number", "description": "Outstanding mortgage in SGD"},
        "cpf_used_with_interest": {"type": "number",
                                   "description": "CPF used for the property incl. accrued interest (refunded to CPF on sale)"},
        "years_owned": {"type": "number"},
        "plan": {"type": "string", "enum": ["sell", "keep"]},
    },
    "required": ["type", "estimated_value", "plan"],
}

TOOLS = [
    {
        "name": "analyze_property_options",
        "description": (
            "Run the eligibility and affordability analysis for a Singapore property buyer. "
            "Returns each segment (HDB resale, new-launch EC, resale private, new-launch private, landed) "
            "ranked by suitability, with eligibility reasons, maximum affordable price, stamp duties, "
            "an illustrative monthly instalment and notes. Call it once the core profile is known, "
            "and again whenever an assumption changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "residency": {"type": "string", "enum": ["SC", "PR", "FOREIGNER"],
                              "description": "Main buyer's residency"},
                "co_applicant_residency": {"type": "string", "enum": ["SC", "PR", "FOREIGNER"],
                                           "description": "Co-buyer's residency, omit if buying alone"},
                "household_type": {"type": "string", "enum": ["single", "married_couple", "other_joint"]},
                "age": {"type": "integer", "description": "Main buyer's age"},
                "monthly_income": {"type": "number", "description": "Gross monthly household income in SGD"},
                "existing_monthly_debt": {"type": "number", "description": "Existing monthly debt repayments in SGD"},
                "cpf_oa_balance": {"type": "number", "description": "Combined CPF OA balance in SGD"},
                "cash_savings": {"type": "number", "description": "Cash available for the purchase in SGD"},
                "current_property": _PROPERTY_SCHEMA,
                "other_properties_count": {"type": "integer",
                                           "description": "Number of other residential properties owned (besides current_property)"},
                "purpose": {"type": "string", "enum": ["own_stay", "investment"]},
                "timeline": {"type": "string", "enum": ["immediate", "flexible"]},
                "years_since_disposed_private": {"type": "number",
                                                 "description": "If they sold a private property in the past 3 years, how long ago"},
            },
            "required": ["residency", "age", "monthly_income", "cpf_oa_balance", "cash_savings"],
        },
    },
    {
        "name": "save_lead",
        "description": (
            "Save the client's contact details so the property agent can follow up. Only call this after "
            "the client has agreed to be contacted and given their name and phone number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "preferred_contact_time": {"type": "string"},
                "summary": {"type": "string",
                            "description": "2-4 sentences: the client's situation, budget and recommended options"},
            },
            "required": ["name", "phone", "summary"],
        },
    },
    {
        "name": "calculate_stamp_duty",
        "description": "Compute Buyer's Stamp Duty and ABSD for a specific purchase price.",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Purchase price in SGD"},
                "residency": {"type": "string", "enum": ["SC", "PR", "FOREIGNER"],
                              "description": "Residency used for ABSD (married couples with an SC are treated as SC)"},
                "property_count_after_purchase": {"type": "integer",
                                                  "description": "1 for first property, 2 for second, 3 for third or more"},
            },
            "required": ["price", "residency", "property_count_after_purchase"],
        },
    },
]


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute a tool call. Returns (json_result, is_error)."""
    try:
        if name == "analyze_property_options":
            return json.dumps(analyse(ClientProfile.from_dict(tool_input))), False
        if name == "calculate_stamp_duty":
            return json.dumps(stamp_duty_breakdown(
                float(tool_input["price"]),
                str(tool_input["residency"]).upper(),
                int(tool_input["property_count_after_purchase"]),
            )), False
        if name == "save_lead":
            return json.dumps(save_lead(tool_input)), False
        return f"Unknown tool: {name}", True
    except (ProfileError, KeyError, ValueError, TypeError, OSError) as exc:
        return f"Invalid input: {exc}", True


LEADS_FILE = os.environ.get("LEADS_FILE", "leads.jsonl")
LEAD_WEBHOOK_URL = os.environ.get("LEAD_WEBHOOK_URL", "")
log = logging.getLogger(__name__)


def save_lead(lead: dict) -> dict:
    """Append a lead to a JSON-lines file. Replace this with your CRM or email integration."""
    name, phone = str(lead.get("name", "")).strip(), str(lead.get("phone", "")).strip()
    if not name or not phone:
        raise ValueError("name and phone are required")
    record = {
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": name[:200],
        "phone": phone[:50],
        "email": str(lead.get("email", ""))[:200],
        "preferred_contact_time": str(lead.get("preferred_contact_time", ""))[:200],
        "summary": str(lead.get("summary", ""))[:2000],
    }
    with open(LEADS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    if LEAD_WEBHOOK_URL:
        _post_webhook(record)
    return {"saved": True, "message": "Lead saved. Tell the client the agent will be in touch."}


def _post_webhook(record: dict):
    """Forward a lead to Google Sheets (Apps Script), Zapier, Make, etc. Failures are logged, not raised."""
    req = urllib.request.Request(LEAD_WEBHOOK_URL, data=json.dumps(record).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as exc:  # the lead is already in LEADS_FILE
        log.warning("Lead webhook failed: %s", exc)


class PropertyAdvisorAgent:
    """Multi-turn chat session with tool use."""

    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL,
                 on_tool_call: Callable[[str, dict], None] | None = None):
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.messages: list = []
        self.on_tool_call = on_tool_call

    def _create(self):
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=self.messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            cache_control={"type": "ephemeral"},
            # Server-side fallback: if the request is declined by a safety
            # classifier, the API retries it on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

    def send(self, user_text: str, max_tool_rounds: int = 8) -> str:
        """Send a user message and return Claude's reply text."""
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(max_tool_rounds):
            response = self._create()
            # Keep the full content (thinking, tool_use, fallback blocks) in history.
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                return "Sorry, I can't help with that request. Please contact the agent directly."
            if response.stop_reason == "max_tokens":
                return _text(response) + "\n[Response truncated]"
            if response.stop_reason != "tool_use":
                return _text(response)

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if self.on_tool_call:
                    self.on_tool_call(block.name, block.input)
                content, is_error = run_tool(block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": content, "is_error": is_error})
            self.messages.append({"role": "user", "content": results})
        return "Sorry, I got stuck working that out. Could you rephrase or give me the details again?"


def _text(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()
