"""Command-line entry points.

  python -m property_agent chat               # conversational agent (needs Claude API credentials)
  python -m property_agent quick              # offline questionnaire, no API needed
  python -m property_agent analyze file.json  # analyse a saved profile, prints text (or --json)
"""

from __future__ import annotations

import argparse
import json
import sys

from .advisor import analyse, format_report
from .profile import ClientProfile, ProfileError


def _ask(prompt: str, cast=str, default=None, choices=None):
    hint = f" [{default}]" if default is not None else ""
    if choices:
        hint = f" ({'/'.join(choices)})" + hint
    while True:
        raw = input(f"{prompt}{hint}: ").strip()
        if not raw and default is not None:
            return default
        if choices and raw.lower() not in [c.lower() for c in choices]:
            print(f"  Please enter one of: {', '.join(choices)}")
            continue
        try:
            return cast(raw.replace(",", "").replace("$", "")) if cast is not str else raw
        except ValueError:
            print("  Please enter a number.")


def questionnaire() -> dict:
    print("\nSingapore Property Options - quick assessment\n")
    d = {
        "residency": _ask("Main buyer residency", choices=["SC", "PR", "FOREIGNER"]).upper(),
        "age": _ask("Main buyer age", int),
    }
    if _ask("Buying with someone?", choices=["y", "n"], default="n").lower() == "y":
        d["co_applicant_residency"] = _ask("Co-buyer residency", choices=["SC", "PR", "FOREIGNER"]).upper()
        married = _ask("Married couple?", choices=["y", "n"], default="y").lower() == "y"
        d["household_type"] = "married_couple" if married else "other_joint"
    d["monthly_income"] = _ask("Gross monthly household income (S$)", float)
    d["existing_monthly_debt"] = _ask("Existing monthly debt repayments (S$)", float, 0.0)
    d["cpf_oa_balance"] = _ask("Combined CPF OA balance (S$)", float, 0.0)
    d["cash_savings"] = _ask("Cash available for purchase (S$)", float, 0.0)
    if _ask("Own a property now?", choices=["y", "n"], default="n").lower() == "y":
        d["current_property"] = {
            "type": _ask("  Type", choices=["HDB", "EC", "PRIVATE", "LANDED"]).upper(),
            "estimated_value": _ask("  Estimated value (S$)", float),
            "outstanding_loan": _ask("  Outstanding loan (S$)", float, 0.0),
            "cpf_used_with_interest": _ask("  CPF used incl. accrued interest (S$)", float, 0.0),
            "years_owned": _ask("  Years owned", float, 0.0),
            "plan": _ask("  Sell or keep it?", choices=["sell", "keep"], default="sell").lower(),
        }
    d["purpose"] = _ask("Purpose", choices=["own_stay", "investment"], default="own_stay").lower()
    d["timeline"] = _ask("Timeline", choices=["immediate", "flexible"], default="flexible").lower()
    return d


def cmd_quick(_args):
    profile = ClientProfile.from_dict(questionnaire())
    print()
    print(format_report(analyse(profile)))


def cmd_analyze(args):
    with open(args.file) as fh:
        profile = ClientProfile.from_dict(json.load(fh))
    report = analyse(profile)
    print(json.dumps(report, indent=2) if args.json else format_report(report))


def cmd_chat(_args):
    from .agent import PropertyAdvisorAgent

    def show_tool(name, _input):
        print(f"  [running {name}...]")

    agent = PropertyAdvisorAgent(on_tool_call=show_tool)
    print("Property advisor - type 'quit' to exit.\n")
    print("Agent: Hi! I can help you work out which property type suits your next move. "
          "To start, are you a Singapore Citizen, PR, or foreigner, and are you buying alone or with someone?\n")
    agent.messages.append({"role": "user", "content": "Hi, I'm looking at my property options."})
    agent.messages.append({"role": "assistant", "content":
                           "Hi! I can help you work out which property type suits your next move. To start, are "
                           "you a Singapore Citizen, PR, or foreigner, and are you buying alone or with someone?"})
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in ("quit", "exit"):
            break
        if not text:
            continue
        print(f"\nAgent: {agent.send(text)}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="property_agent", description="Singapore property options advisor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("chat", help="Chat with the Claude-powered advisor").set_defaults(func=cmd_chat)
    sub.add_parser("quick", help="Offline questionnaire (no API key needed)").set_defaults(func=cmd_quick)
    p_an = sub.add_parser("analyze", help="Analyse a client profile JSON file")
    p_an.add_argument("file")
    p_an.add_argument("--json", action="store_true", help="Print raw JSON report")
    p_an.set_defaults(func=cmd_analyze)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ProfileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
