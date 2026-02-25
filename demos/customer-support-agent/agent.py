"""
Acme Analytics Customer Support Agent
======================================
ReAct-style tool-calling agent using Kimi K2 (OpenAI-compatible API)
with CortexOS as the persistent memory layer.

Run:
    python agent.py                    # interactive mode
    python agent.py --demo             # run a scripted 3-turn demo
    python agent.py --customer sarah   # start with a different customer
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ── Load .env ──────────────────────────────────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── Validate key ───────────────────────────────────────────────────────────
_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
if not _API_KEY or _API_KEY == "your-kimi-k2-api-key-here":
    sys.exit(
        "\nERROR: Set MOONSHOT_API_KEY in demos/customer-support-agent/.env\n"
        "       Get your key at https://platform.moonshot.cn\n"
    )

from openai import OpenAI

from memory import CortexMemory
from tools import check_account_status, escalate_to_human, search_docs

# ── Colours ────────────────────────────────────────────────────────────────
_BOLD    = "\033[1m"
_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_MAGENTA = "\033[95m"
_DIM     = "\033[2m"
_RESET   = "\033[0m"
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _USE_COLOR else text


# ── OpenAI client pointed at Kimi K2 ──────────────────────────────────────

_client = OpenAI(
    api_key=_API_KEY,
    base_url="https://api.moonshot.ai/v1",
)
_MODEL = "kimi-k2-0905-preview"


# ── Tool definitions for the API ───────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search the Acme Analytics documentation knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to look up: 'dashboard', 'billing', 'api', 'seats', 'integrations'",
                    }
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_account_status",
            "description": "Look up a customer's account status, plan, seats, and open support tickets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "First or full name of the customer (e.g. 'John', 'Sarah')",
                    }
                },
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate a complex issue to a human support agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Customer name"},
                    "issue_summary": {"type": "string", "description": "Brief description of the issue"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "urgent"],
                        "description": "Escalation priority",
                    },
                },
                "required": ["customer_name", "issue_summary"],
            },
        },
    },
]

_TOOL_DISPATCH = {
    "search_docs": lambda args: search_docs.invoke(args),
    "check_account_status": lambda args: check_account_status.invoke(args),
    "escalate_to_human": lambda args: escalate_to_human.invoke(args),
}


# ── Tool-calling loop ──────────────────────────────────────────────────────

def _run_agent(messages: list[dict], verbose: bool = True) -> str:
    """
    Single agentic turn: call Kimi K2, execute any tool calls, loop until
    the model produces a final text response.
    """
    for _ in range(8):  # max 8 tool calls per turn
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=_TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1024,
        )
        msg = response.choices[0].message

        # No tool calls → final answer
        if not msg.tool_calls:
            return msg.content or ""

        # Append the assistant's tool-call message
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        # Execute each tool call
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            if verbose:
                print(f"  {_c(_DIM, f'[tool] {fn_name}({json.dumps(fn_args)})')}")

            try:
                tool_fn = _TOOL_DISPATCH.get(fn_name)
                if tool_fn:
                    result = tool_fn(fn_args)
                else:
                    result = f"Unknown tool: {fn_name}"
            except Exception as exc:
                result = f"Tool error: {exc}"

            if verbose:
                # Show first 120 chars of result
                preview = str(result)[:120].replace("\n", " ")
                print(f"  {_c(_DIM, f'    → {preview}...' if len(str(result)) > 120 else f'    → {preview}')}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })

    return "I wasn't able to complete that in time. Please try again or contact support directly."


# ── Session ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are Aria, a friendly and knowledgeable customer support agent for Acme Analytics \
(a SaaS analytics platform).

Your job:
- Help customers with questions about their account, billing, and the product
- Use your tools to check account status and search documentation
- Escalate genuinely complex issues to a human agent

Always be concise, warm, and professional. Sign off as "Aria from Acme Support".

You have access to recalled long-term memory about this customer (injected per turn).
Use it to personalise your response — don't re-ask for information you already know."""


class SupportSession:
    def __init__(self, customer: str = "john", verbose: bool = True, api_key: str | None = None):
        self.customer = customer
        self.customer_tag = f"customer:{customer.lower()}"
        self.verbose = verbose
        self.memory = CortexMemory(api_key=api_key)
        self.conversation: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        print(f"\n{_c(_BOLD + _CYAN, '╔══════════════════════════════════════════════════════════╗')}")
        print(f"{_c(_BOLD + _CYAN,   '║        Acme Analytics Customer Support (CortexOS)        ║')}")
        print(f"{_c(_BOLD + _CYAN,   '╚══════════════════════════════════════════════════════════╝')}")
        print(f"{_c(_DIM, f'LLM: Kimi K2 (moonshot-v1-8k) | Memory: CortexOS EAS')}\n")

        # Seed customer context
        print(f"{_c(_YELLOW, f'[memory] Seeding context for customer: {customer}...')}")
        ids = self.memory.seed_customer_context(customer)
        if ids:
            print(f"{_c(_DIM, f'[memory] Stored {len(ids)} facts → CortexOS')}\n")

    def turn(self, user_input: str) -> str:
        print(f"\n{_c(_BOLD, 'Customer:')} {user_input}")

        # ── 1. Recall relevant memories ────────────────────────────────────
        recalled = self.memory.recall_context(
            query=user_input,
            top_k=5,
            customer_tag=self.customer_tag,
        )
        context_block = self.memory.format_context_block(recalled)
        if recalled and self.verbose:
            print(f"{_c(_DIM, f'[memory] Recalled {len(recalled)} facts:')}")
            for r in recalled:
                print(f"{_c(_DIM, f'  [{r.score:.2f}] {r.memory.content[:80]}')}")

        # ── 2. Build messages with injected memory context ─────────────────
        memory_injection = (
            f"\n\n## Recalled long-term memory (CortexOS)\n{context_block}"
            if recalled else ""
        )
        turn_messages = list(self.conversation)
        turn_messages.append({
            "role": "user",
            "content": user_input + memory_injection,
        })

        # ── 3. Run Kimi K2 with tool calls ────────────────────────────────
        response = _run_agent(turn_messages, verbose=self.verbose)

        print(f"\n{_c(_BOLD + _GREEN, 'Aria:')} {response}")

        # Append clean messages (without memory injection) to history
        self.conversation.append({"role": "user", "content": user_input})
        self.conversation.append({"role": "assistant", "content": response})

        # ── 4. Remember key facts from this turn ───────────────────────────
        self._remember_turn_facts(user_input, response)

        # ── 5. EAS Attribution — which memories drove the response? ────────
        self.memory.attribute_turn(
            query=user_input,
            response=response,
            recalled_results=recalled,
        )

        return response

    def _remember_turn_facts(self, query: str, response: str) -> None:
        q_lower = query.lower()
        r_lower = response.lower()
        facts: list[tuple[str, list[str], float]] = []

        if any(w in q_lower for w in ["slow", "broken", "error", "crash", "not working", "issue", "problem", "bug"]):
            facts.append((
                f"Customer {self.customer.title()} reported issue: {query[:120]}",
                [self.customer_tag, "issue"],
                0.85,
            ))

        if any(w in q_lower for w in ["prefer", "want", "like", "email", "phone", "slack"]):
            facts.append((
                f"Customer {self.customer.title()} preference noted: {query[:120]}",
                [self.customer_tag, "preferences"],
                0.8,
            ))

        if "ESC-" in response or "escalat" in r_lower:
            facts.append((
                f"Issue escalated for {self.customer.title()}: {query[:100]}",
                [self.customer_tag, "escalation"],
                0.9,
            ))

        for content, tags, importance in facts:
            mid = self.memory.remember_fact(content, tags=tags, importance=importance)
            if self.verbose:
                print(f"{_c(_DIM, f'[memory] Stored: {content[:65]}... ({mid[:8]})')}")

    def close(self) -> None:
        self.memory.close()


# ── Demo script ────────────────────────────────────────────────────────────

_DEMO_TURNS = [
    "Hi, I'm John. Is my dashboard issue from last week fixed yet?",
    "Can you remind me what plan I'm on and how many seats I have left?",
    "The dashboard is still slow today. Can you escalate this as urgent?",
]


def run_demo(customer: str = "john", api_key: str | None = None) -> None:
    session = SupportSession(customer=customer, api_key=api_key)
    print(f"\n{_c(_BOLD + _MAGENTA, f'── Scripted demo: {len(_DEMO_TURNS)} turns ──')}\n")
    try:
        for i, turn_text in enumerate(_DEMO_TURNS, 1):
            print(f"{_c(_BOLD + _MAGENTA, f'─── Turn {i}/{len(_DEMO_TURNS)} ───────────────────────────────────────')}")
            session.turn(turn_text)
            print()
    finally:
        session.close()
    print(f"{_c(_BOLD + _CYAN, 'Demo complete.')}")


def run_interactive(customer: str = "john", api_key: str | None = None) -> None:
    session = SupportSession(customer=customer, api_key=api_key)
    print(f"{_c(_DIM, 'Type your message (or \"quit\" to exit)')}\n")
    try:
        while True:
            try:
                user_input = input(_c(_BOLD, "\nYou: ")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue
            if user_input.lower() in {"quit", "exit", "q"}:
                break
            session.turn(user_input)
    finally:
        session.close()
        print(f"\n{_c(_DIM, 'Session ended.')}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acme Analytics Support Agent + CortexOS")
    parser.add_argument("--demo", action="store_true", help="Run scripted 3-turn demo")
    parser.add_argument("--customer", default="john", help="Customer to seed context for")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CORTEX_API_KEY", ""),
        help="CortexOS API key (or set CORTEX_API_KEY env var)",
    )
    args = parser.parse_args()

    if args.demo:
        run_demo(customer=args.customer, api_key=args.api_key or None)
    else:
        run_interactive(customer=args.customer, api_key=args.api_key or None)
