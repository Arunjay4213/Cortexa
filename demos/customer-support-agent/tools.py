"""
Acme Analytics — fake tools available to the support agent.
These simulate real SaaS product operations without any external dependencies.
"""

from __future__ import annotations

from langchain_core.tools import tool

# ── Fake knowledge base ────────────────────────────────────────────────────

_DOCS: dict[str, str] = {
    "dashboard": (
        "The Acme Analytics dashboard refreshes every 60 seconds by default. "
        "If loading is slow, check your browser's network tab for large payload sizes. "
        "Known issue (Feb 2026): dashboard may be slow for accounts with > 500 widgets. "
        "Workaround: reduce the number of pinned widgets or switch to list view."
    ),
    "billing": (
        "Acme Analytics pricing: Starter $29/mo (1 seat), Pro $79/mo (up to 5 seats), "
        "Enterprise custom pricing. Billing cycles are monthly or annual (20% discount). "
        "Invoices are sent on the 1st of each month. Refunds available within 30 days."
    ),
    "api": (
        "The Acme Analytics REST API is documented at https://docs.acme.example/api. "
        "Rate limits: 1,000 requests/min on Pro, 10,000 on Enterprise. "
        "API keys are rotated every 90 days. Use OAuth 2.0 for production integrations."
    ),
    "seats": (
        "Seats can be added from Settings → Team → Add Members. "
        "Removing a seat takes effect at end of current billing cycle. "
        "Pro plan: up to 5 seats. Need more? Upgrade to Enterprise."
    ),
    "integrations": (
        "Acme Analytics integrates with Slack, Jira, GitHub, PagerDuty, and Salesforce. "
        "Webhooks are available on Pro and Enterprise plans. "
        "OAuth apps must be approved by your workspace admin."
    ),
}

_ACCOUNTS: dict[str, dict] = {
    "john": {
        "name": "John Smith",
        "email": "john@acme-customer.com",
        "plan": "Pro",
        "seats_used": 3,
        "seats_total": 5,
        "status": "active",
        "open_tickets": ["TKT-1042 (dashboard slow — investigating)"],
        "billing_ok": True,
        "joined": "2024-06-10",
    },
    "sarah": {
        "name": "Sarah Chen",
        "email": "sarah@bigcorp.com",
        "plan": "Enterprise",
        "seats_used": 47,
        "seats_total": 100,
        "status": "active",
        "open_tickets": [],
        "billing_ok": True,
        "joined": "2023-01-15",
    },
    "mike": {
        "name": "Mike Rodriguez",
        "email": "mike@startup.io",
        "plan": "Starter",
        "seats_used": 1,
        "seats_total": 1,
        "status": "payment_failed",
        "open_tickets": ["TKT-1089 (payment failure — card declined)"],
        "billing_ok": False,
        "joined": "2025-11-20",
    },
}

_ESCALATION_LOG: list[dict] = []


# ── LangChain tools ────────────────────────────────────────────────────────


@tool
def search_docs(topic: str) -> str:
    """
    Search the Acme Analytics documentation.

    Args:
        topic: What to look up — e.g. 'dashboard', 'billing', 'api', 'seats', 'integrations'
    """
    topic_lower = topic.lower()
    for key, content in _DOCS.items():
        if key in topic_lower or topic_lower in key:
            return f"[Docs: {key}]\n{content}"
    # Fuzzy match — return closest
    for key, content in _DOCS.items():
        words = set(topic_lower.split())
        if words & set(key):
            return f"[Docs: {key}]\n{content}"
    return (
        f"No documentation found for '{topic}'. "
        f"Available topics: {', '.join(_DOCS.keys())}. "
        "Try one of those or escalate to a human agent."
    )


@tool
def check_account_status(customer_name: str) -> str:
    """
    Look up a customer's account status, plan, and open support tickets.

    Args:
        customer_name: First name or full name of the customer (e.g. 'John', 'Sarah')
    """
    key = customer_name.lower().split()[0]
    account = _ACCOUNTS.get(key)
    if not account:
        return (
            f"No account found for '{customer_name}'. "
            f"Known accounts: {', '.join(a['name'] for a in _ACCOUNTS.values())}."
        )
    tickets = account["open_tickets"]
    ticket_str = "\n  - ".join(tickets) if tickets else "None"
    billing = "OK" if account["billing_ok"] else "PAYMENT FAILED — action required"
    return (
        f"Account: {account['name']} ({account['email']})\n"
        f"Plan: {account['plan']}  |  Seats: {account['seats_used']}/{account['seats_total']}\n"
        f"Status: {account['status']}  |  Billing: {billing}\n"
        f"Open tickets:\n  - {ticket_str}\n"
        f"Member since: {account['joined']}"
    )


@tool
def escalate_to_human(
    customer_name: str,
    issue_summary: str,
    priority: str = "normal",
) -> str:
    """
    Escalate a complex issue to a human support agent.

    Args:
        customer_name: Name of the customer
        issue_summary: Brief description of the issue needing escalation
        priority: 'low', 'normal', or 'urgent'
    """
    ticket_id = f"ESC-{1000 + len(_ESCALATION_LOG) + 1}"
    record = {
        "ticket_id": ticket_id,
        "customer": customer_name,
        "issue": issue_summary,
        "priority": priority,
    }
    _ESCALATION_LOG.append(record)
    eta = {"low": "2 business days", "normal": "4 hours", "urgent": "30 minutes"}[priority]
    return (
        f"Escalation created: {ticket_id}\n"
        f"Customer: {customer_name}\n"
        f"Priority: {priority.upper()} — a human agent will respond within {eta}.\n"
        f"Issue: {issue_summary}"
    )
