"""
CortexOS memory layer for the support agent.

Wraps cortexos.Cortex to provide:
  - remember_fact()   → store a distilled fact after each turn
  - recall_context()  → semantic search before each response
  - attribute_turn()  → EAS score + pretty-print which memories drove the response
"""

from __future__ import annotations

import os
import sys
from typing import Any

from cortexos import Cortex
from cortexos.types import Attribution, RecallResult

# ── Colour helpers (no external deps) ─────────────────────────────────────

_BOLD  = "\033[1m"
_GREEN = "\033[92m"
_CYAN  = "\033[96m"
_YELLOW= "\033[93m"
_DIM   = "\033[2m"
_RESET = "\033[0m"

_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _USE_COLOR else text


# ── CortexMemory ───────────────────────────────────────────────────────────

class CortexMemory:
    """Thin facade over cortexos.Cortex tailored for the support agent."""

    def __init__(
        self,
        agent_id: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self._cx = Cortex(
            agent_id=agent_id or os.environ.get("CORTEX_AGENT_ID", "support-bot"),
            base_url=base_url or os.environ.get("CORTEX_BASE_URL", "http://localhost:8000"),
            api_key=api_key or os.environ.get("CORTEX_API_KEY", ""),
        )
        self._turn_memories: list[str] = []  # IDs stored this turn

    # ── Store ──────────────────────────────────────────────────────────────

    def remember_fact(
        self,
        content: str,
        tags: list[str] | None = None,
        importance: float = 0.7,
    ) -> str:
        """Store a distilled fact and return its memory ID."""
        mem = self._cx.remember(content, importance=importance, tags=tags or [])
        self._turn_memories.append(mem.id)
        return mem.id

    def seed_customer_context(self, customer: str) -> list[str]:
        """
        Pre-load a realistic set of facts about a customer so the demo
        starts with a non-empty memory store.  Returns list of IDs.
        """
        facts: dict[str, dict[str, Any]] = {
            "john": [
                ("Customer John has a Pro plan with 3 seats used out of 5.",
                 ["customer:john", "account", "plan"], 0.9),
                ("John reported the Acme Analytics dashboard loading slowly on Feb 15 2026.",
                 ["customer:john", "issue", "dashboard"], 0.95),
                ("John's open ticket TKT-1042 is under investigation by the engineering team.",
                 ["customer:john", "ticket:TKT-1042", "dashboard"], 0.9),
                ("John prefers email communication for all support updates.",
                 ["customer:john", "preferences", "communication"], 0.8),
                ("John's account billing is in good standing; no payment issues.",
                 ["customer:john", "account", "billing"], 0.7),
            ],
        }
        customer_lower = customer.lower()
        ids = []
        for content, tags, importance in facts.get(customer_lower, []):
            ids.append(self.remember_fact(content, tags=tags, importance=importance))
        return ids

    # ── Recall ─────────────────────────────────────────────────────────────

    def recall_context(
        self,
        query: str,
        top_k: int = 5,
        customer_tag: str | None = None,
    ) -> list[RecallResult]:
        """Semantic search; optionally filter to a specific customer's tags."""
        tags = [customer_tag] if customer_tag else None
        results = self._cx.recall(query, top_k=top_k, tags=tags)
        if not results:
            # fall back without tag filter
            results = self._cx.recall(query, top_k=top_k)
        return results

    def format_context_block(self, results: list[RecallResult]) -> str:
        """Return a formatted string suitable for injecting into the system prompt."""
        if not results:
            return "(no relevant memories found)"
        lines = []
        for r in results:
            score_bar = "█" * int(r.score * 10) + "░" * (10 - int(r.score * 10))
            lines.append(f"  [{r.score:.2f} {score_bar}] {r.memory.content}")
        return "\n".join(lines)

    # ── Attribution ────────────────────────────────────────────────────────

    def attribute_turn(
        self,
        query: str,
        response: str,
        recalled_results: list[RecallResult],
    ) -> Attribution | None:
        """Run EAS attribution and pretty-print a score table."""
        if not recalled_results:
            return None

        memory_ids = [r.memory.id for r in recalled_results]
        try:
            attr = self._cx.attribute(query=query, response=response, memory_ids=memory_ids)
        except Exception as exc:
            print(f"{_c(_YELLOW, '[attribution error]')} {exc}")
            return None

        # ── Pretty print ───────────────────────────────────────────────────
        print(f"\n{_c(_BOLD, '── Attribution (EAS) ─────────────────────────────────────')}")
        print(f"{_c(_DIM, f'  transaction: {attr.transaction_id}')}")

        # Sort by score descending
        sorted_scores = sorted(attr.scores.items(), key=lambda x: x[1], reverse=True)
        for mid, score in sorted_scores:
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            # Find content for this memory
            content = next(
                (r.memory.content for r in recalled_results if r.memory.id == mid),
                mid,
            )
            # Colour: green > 0.3, yellow 0.1–0.3, dim < 0.1
            if score > 0.3:
                colour = _GREEN
            elif score > 0.1:
                colour = _YELLOW
            else:
                colour = _DIM
            print(f"  {_c(colour, f'{score:.2f}')} {bar}  {content[:75]}")

        print(f"{_c(_BOLD, '─────────────────────────────────────────────────────────────')}\n")
        return attr

    # ── Cleanup ────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._cx.close()

    def __enter__(self) -> "CortexMemory":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
