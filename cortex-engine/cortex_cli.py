#!/usr/bin/env python3
"""CortexOS Shell — interactive CLI for exploring agent memory and attribution.

Usage:
    python cortex_cli.py
    python cortex_cli.py --url http://localhost:8000 --key sk-cortex-...
"""

from __future__ import annotations

import argparse
import os
import readline  # noqa: F401  — enables arrow-key history in input()
import sys
import textwrap
from datetime import datetime
from typing import Any

import httpx

# ── ANSI colour helpers ──────────────────────────────────────────────────────

CYAN    = "\033[36m"
GREEN   = "\033[32m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
YELLOW  = "\033[33m"
DIM     = "\033[2m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

def _c(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"

def _short_id(mid: str) -> str:
    return mid[:12] if mid else "?"

def _trunc(text: str, n: int = 52) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:n] + "…" if len(text) > n else text

def _score_bar(score: float, width: int = 20) -> str:
    filled = int(score * width)
    return _c("█" * filled, GREEN) + _c("░" * (width - filled), DIM)

def _ts(iso: str | None) -> str:
    if not iso:
        return _c("—", DIM)
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return _c(dt.strftime("%Y-%m-%d %H:%M"), DIM)
    except Exception:
        return _c(str(iso)[:16], DIM)


# ── Box-drawing table ────────────────────────────────────────────────────────

def _table(headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
    """Print a Unicode box-drawn table."""
    if not col_widths:
        col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=4)) for i, h in enumerate(headers)]
        col_widths = [min(w, 56) for w in col_widths]

    def _pad(val: str, w: int) -> str:
        # Strip ANSI for length calculation
        import re
        visible = re.sub(r"\033\[[0-9;]*m", "", str(val))
        pad = w - len(visible)
        return str(val) + " " * max(0, pad)

    top    = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    mid    = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    bottom = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    print(top)
    print("│ " + " │ ".join(_pad(h, col_widths[i]) for i, h in enumerate(headers)) + " │")
    print(mid)
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cells.append(_pad(str(cell), col_widths[i]))
        print("│ " + " │ ".join(cells) + " │")
    print(bottom)


# ── HTTP client ──────────────────────────────────────────────────────────────

class CortexAPI:
    """Thin HTTP wrapper for CortexOS engine."""

    def __init__(self, base_url: str, api_key: str | None):
        self.base_url = base_url.rstrip("/")
        self._prefix = "/api/v1"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=30.0)

    def close(self):
        self._client.close()

    def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get(f"{self._prefix}{path}", params=clean)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict | None = None) -> Any:
        resp = self._client.post(f"{self._prefix}{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str) -> int:
        resp = self._client.delete(f"{self._prefix}{path}")
        resp.raise_for_status()
        return resp.status_code

    def healthz(self) -> bool:
        try:
            resp = self._client.get("/healthz")
            return resp.status_code == 200
        except Exception:
            return False


# ── Command handlers ─────────────────────────────────────────────────────────

class CortexShell:
    def __init__(self, api: CortexAPI):
        self.api = api
        self._mem_page = 0
        self._mem_cache: list[dict] = []
        self._mem_total = 0
        self._mem_agent: str | None = None
        self._mem_tag: str | None = None

    # ── memories ──────────────────────────────────────────────────────────

    def cmd_memories(self, args: list[str]):
        agent_id = None
        tag = None
        for i, a in enumerate(args):
            if a == "--agent" and i + 1 < len(args):
                agent_id = args[i + 1]
            if a == "--tag" and i + 1 < len(args):
                tag = args[i + 1]

        self._mem_agent = agent_id
        self._mem_tag = tag
        self._mem_page = 0
        self._fetch_memories_page()

    def _fetch_memories_page(self):
        params: dict[str, Any] = {
            "offset": self._mem_page * 20,
            "limit": 20,
            "sort_by": "created_at",
            "order": "desc",
        }
        if self._mem_agent:
            params["agent_id"] = self._mem_agent

        data = self.api.get("/memories", **params)
        items = data.get("items", [])
        self._mem_total = data.get("total", 0)
        self._mem_cache = items

        if self._mem_tag:
            items = [m for m in items if self._mem_tag in (m.get("metadata", {}).get("_tags", []))]

        if not items:
            print(_c("  No memories found.", DIM))
            return

        rows = []
        for m in items:
            mid = _c(_short_id(m["id"]), CYAN)
            agent = _c(m.get("agent_id", "?"), MAGENTA)
            content = _trunc(m.get("content", ""), 50)
            rows.append([mid, agent, content])

        print(f"\n  {_c(str(self._mem_total), BOLD)} memories total  "
              f"{_c(f'(page {self._mem_page + 1})', DIM)}")
        _table(["ID", "Agent", "Content"], rows, [12, 20, 50])

        start = self._mem_page * 20 + 1
        end = min(start + 19, self._mem_total)
        print(f"  Showing {start}–{end} of {self._mem_total}.  "
              f"{_c('n', BOLD)}=next  {_c('p', BOLD)}=prev")

    def cmd_next_page(self):
        max_page = (self._mem_total - 1) // 20 if self._mem_total > 0 else 0
        if self._mem_page < max_page:
            self._mem_page += 1
            self._fetch_memories_page()
        else:
            print(_c("  Already on last page.", DIM))

    def cmd_prev_page(self):
        if self._mem_page > 0:
            self._mem_page -= 1
            self._fetch_memories_page()
        else:
            print(_c("  Already on first page.", DIM))

    # ── memory <id> ───────────────────────────────────────────────────────

    def cmd_memory(self, memory_id: str):
        try:
            data = self.api.get(f"/memories/{memory_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(_c(f"  Memory {memory_id} not found.", RED))
            else:
                print(_c(f"  Error: {e}", RED))
            return

        mem = data.get("memory", data)
        profile = data.get("profile")

        print(f"\n  {_c('Memory', BOLD)} {_c(mem['id'], CYAN)}")
        print(f"  Agent:      {_c(mem.get('agent_id', '?'), MAGENTA)}")
        print(f"  Tier:       {mem.get('tier', '?')}")
        print(f"  Importance: {mem.get('criticality', 0.5)}")
        tags = mem.get("metadata", {}).get("_tags", [])
        if tags:
            print(f"  Tags:       {', '.join(tags)}")
        meta = {k: v for k, v in mem.get("metadata", {}).items() if k != "_tags"}
        if meta:
            print(f"  Metadata:   {meta}")
        print(f"  Retrievals: {mem.get('retrieval_count', 0)}")
        print(f"  Created:    {_ts(mem.get('created_at'))}")
        print(f"  Accessed:   {_ts(mem.get('last_accessed'))}")
        print(f"\n  {_c('Content:', BOLD)}")
        for line in textwrap.wrap(mem.get("content", ""), 72):
            print(f"    {line}")

        if profile:
            print(f"\n  {_c('Attribution Profile:', BOLD)}")
            print(f"    Mean attribution:  {profile.get('mean_attribution', 0):.4f}")
            print(f"    Total attribution: {profile.get('total_attribution', 0):.4f}")
            print(f"    Retrieval count:   {profile.get('retrieval_count', 0)}")
            print(f"    Trend:             {profile.get('trend', 'stable')}")
        print()

    # ── store ─────────────────────────────────────────────────────────────

    def cmd_store(self, args: list[str]):
        # Parse: store "content" --agent X --tags a,b
        content = None
        agent_id = "cli-manual"
        tags: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--agent" and i + 1 < len(args):
                agent_id = args[i + 1]
                i += 2
            elif args[i] == "--tags" and i + 1 < len(args):
                tags = [t.strip() for t in args[i + 1].split(",")]
                i += 2
            else:
                if content is None:
                    content = args[i].strip('"').strip("'")
                i += 1

        if not content:
            print(_c("  Usage: store \"content\" --agent NAME --tags a,b", YELLOW))
            return

        meta: dict[str, Any] = {}
        if tags:
            meta["_tags"] = tags
        payload = {
            "content": content,
            "agent_id": agent_id,
            "tier": "warm",
            "criticality": 0.5,
            "metadata": meta,
        }
        result = self.api.post("/memories", json=payload)
        mid = result.get("id", "?")
        print(f"  {_c('✓', GREEN)} Stored: {_c(_short_id(mid), CYAN)} ← {_trunc(content, 60)}")

    # ── forget ────────────────────────────────────────────────────────────

    def cmd_forget(self, args: list[str]):
        # forget <id>  or  forget --agent X --all
        if "--all" in args:
            agent_id = None
            for i, a in enumerate(args):
                if a == "--agent" and i + 1 < len(args):
                    agent_id = args[i + 1]
            if not agent_id:
                print(_c("  Usage: forget --agent AGENT_ID --all", YELLOW))
                return
            # List memories for this agent, confirm, then delete each
            data = self.api.get("/memories", agent_id=agent_id, limit=200)
            items = data.get("items", [])
            if not items:
                print(_c(f"  No memories for agent {agent_id}.", DIM))
                return
            confirm = input(f"  Delete {_c(str(len(items)), RED)} memories for "
                          f"{_c(agent_id, MAGENTA)}? [y/N] ").strip().lower()
            if confirm != "y":
                print("  Cancelled.")
                return
            for m in items:
                try:
                    self.api.delete(f"/memories/{m['id']}")
                except Exception:
                    pass
            print(f"  {_c('✓', GREEN)} Deleted {len(items)} memories.")
            return

        if not args:
            print(_c("  Usage: forget <memory_id>", YELLOW))
            return

        mid = args[0]
        # Try to resolve short ID
        if len(mid) < 36:
            mid = self._resolve_short_id(mid)
            if not mid:
                return

        confirm = input(f"  Delete {_c(_short_id(mid), CYAN)}? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return

        try:
            self.api.delete(f"/memories/{mid}")
            print(f"  {_c('✓', GREEN)} Deleted {_c(_short_id(mid), CYAN)}")
        except httpx.HTTPStatusError as e:
            print(_c(f"  Error: {e.response.status_code}", RED))

    def _resolve_short_id(self, short: str) -> str | None:
        """Try to find a full memory ID matching the short prefix."""
        # Check cached memories first
        for m in self._mem_cache:
            if m.get("id", "").startswith(short):
                return m["id"]
        # Search all
        data = self.api.get("/memories", limit=200)
        for m in data.get("items", []):
            if m.get("id", "").startswith(short):
                return m["id"]
        print(_c(f"  No memory found matching '{short}'", RED))
        return None

    # ── recall ────────────────────────────────────────────────────────────

    def cmd_recall(self, args: list[str]):
        query_parts = []
        agent_id = None
        top_k = 5
        i = 0
        while i < len(args):
            if args[i] == "--agent" and i + 1 < len(args):
                agent_id = args[i + 1]
                i += 2
            elif args[i] == "--top" and i + 1 < len(args):
                top_k = int(args[i + 1])
                i += 2
            else:
                query_parts.append(args[i])
                i += 1

        query = " ".join(query_parts).strip('"').strip("'")
        if not query:
            print(_c("  Usage: recall \"query text\" [--agent X] [--top N]", YELLOW))
            return

        params: dict[str, Any] = {"q": query, "top_k": top_k}
        if agent_id:
            params["agent_id"] = agent_id

        results = self.api.get("/memories/search", **params)
        if not results:
            print(_c("  No results.", DIM))
            return

        print(f"\n  {_c('Recall', BOLD)} for: \"{query}\"\n")
        for item in results:
            score = item.get("similarity", 0.0)
            mem = item.get("memory", {})
            content = _trunc(mem.get("content", ""), 60)
            agent = _c(mem.get("agent_id", "?")[:16], MAGENTA)
            bar = _score_bar(score)
            print(f"  {score:.2f} {bar} {content}")
            print(f"       {_c(_short_id(mem.get('id', '?')), CYAN)} {agent}")
        print()

    # ── agents ────────────────────────────────────────────────────────────

    def cmd_agents(self):
        agents = self.api.get("/agents")
        if not agents:
            print(_c("  No agents found.", DIM))
            return

        rows = []
        for a in agents:
            aid = _c(a.get("agent_id", "?"), MAGENTA)
            mems = str(a.get("total_memories", 0))
            txns = str(a.get("total_transactions", 0))
            avg = f"{a.get('avg_attribution', 0):.3f}"
            last = _ts(a.get("last_active"))
            rows.append([aid, mems, txns, avg, last])

        print(f"\n  {_c(str(len(agents)), BOLD)} agents\n")
        _table(["Agent ID", "Memories", "Txns", "Avg Attr", "Last Active"],
               rows, [22, 8, 6, 9, 18])
        print()

    # ── agent <id> ────────────────────────────────────────────────────────

    def cmd_agent(self, agent_id: str):
        try:
            data = self.api.get(f"/agents/{agent_id}")
        except httpx.HTTPStatusError:
            print(_c(f"  Agent {agent_id} not found.", RED))
            return

        print(f"\n  {_c('Agent', BOLD)} {_c(data.get('agent_id', '?'), MAGENTA)}")
        print(f"  Memories:       {data.get('total_memories', 0)}")
        print(f"  Transactions:   {data.get('total_transactions', 0)}")
        print(f"  Avg attribution: {data.get('avg_attribution', 0):.4f}")
        td = data.get("tier_distribution", {})
        print(f"  Tiers:          hot={td.get('hot', 0)} warm={td.get('warm', 0)} cold={td.get('cold', 0)}")
        tu = data.get("token_usage", {})
        print(f"  Tokens:         in={tu.get('input', 0):,}  out={tu.get('output', 0):,}")
        print(f"  Gini:           {data.get('gini_coefficient', 0):.4f}")
        print(f"  SNR:            {data.get('snr_db', 0):.2f} dB")
        print(f"  Waste rate:     {data.get('waste_rate', 0):.2%}")
        print(f"  Contradictions: {data.get('contradiction_count', 0)}")
        print(f"  Last active:    {_ts(data.get('last_active'))}")

        recent = data.get("recent_transactions", [])
        if recent:
            print(f"\n  {_c('Recent Transactions:', BOLD)}")
            for txn in recent[:5]:
                tid = _c(_short_id(txn.get("id", "?")), CYAN)
                q = _trunc(txn.get("query_text", ""), 50)
                ts_str = _ts(txn.get("created_at"))
                print(f"    {tid} {q}  {ts_str}")
        print()

    # ── attribute ─────────────────────────────────────────────────────────

    def cmd_attribute(self, args: list[str]):
        if args:
            # Show detail for a specific transaction
            txn_id = args[0]
            if len(txn_id) < 36:
                txn_id = self._resolve_short_txn(txn_id)
                if not txn_id:
                    return
            self._show_cama(txn_id)
            return

        # List recent transactions with CAMA scores
        try:
            data = self.api.get("/dashboard/hallucinations", limit=10)
        except Exception:
            # Fallback: list recent transactions
            data = self.api.get("/transactions", limit=10)
            items = data.get("items", [])
            if not items:
                print(_c("  No transactions found.", DIM))
                return
            rows = []
            for t in items:
                tid = _c(_short_id(t.get("id", "?")), CYAN)
                agent = _c(t.get("agent_id", "?"), MAGENTA)
                q = _trunc(t.get("query_text", ""), 40)
                ts_str = _ts(t.get("created_at"))
                rows.append([tid, agent, q, ts_str])
            print(f"\n  Recent transactions:\n")
            _table(["ID", "Agent", "Query", "Time"], rows, [12, 22, 40, 18])
            print()
            return

        if not data:
            print(_c("  No CAMA transactions found.", DIM))
            return

        rows = []
        for t in data:
            tid = _c(_short_id(t.get("transaction_id", "?")), CYAN)
            agent = _c(t.get("agent_id", "?"), MAGENTA)
            hi = t.get("hallucination_index", 0)
            hi_str = _c(f"{hi:.0%}", RED if hi > 0.3 else GREEN)
            q = _trunc(t.get("query", ""), 36)
            ts_str = _ts(t.get("created_at"))
            rows.append([tid, agent, hi_str, q, ts_str])

        print(f"\n  {_c('Attribution Transactions', BOLD)} (CAMA)\n")
        _table(["ID", "Agent", "Halluc%", "Query", "Time"],
               rows, [12, 22, 8, 36, 18])
        print()

    def _show_cama(self, txn_id: str):
        """Show full CAMA detail for a transaction."""
        # First get the transaction info
        try:
            txn_data = self.api.get(f"/transactions/{txn_id}")
        except httpx.HTTPStatusError:
            print(_c(f"  Transaction {txn_id} not found.", RED))
            return

        txn = txn_data.get("transaction", txn_data)
        agent = txn.get("agent_id", "?")

        # Run CAMA (this recomputes, which is the only way to get claim data)
        try:
            cama = self.api.post(f"/attribution/{txn_id}/cama")
        except httpx.HTTPStatusError as e:
            print(_c(f"  CAMA failed: {e.response.text[:200]}", RED))
            return

        claims = cama.get("claims", [])
        hi = cama.get("hallucination_index", 0)
        num_claims = cama.get("num_claims", len(claims))
        grounded = [c for c in claims if not c.get("is_hallucination")]
        hallucinated = [c for c in claims if c.get("is_hallucination")]
        dead = cama.get("dead_memories", [])

        grounded_pct = len(grounded) / num_claims * 100 if num_claims > 0 else 0

        print()
        top = f"┌─ Transaction: {_short_id(txn_id)} ─ Agent: {agent} "
        top += "─" * max(0, 60 - len(top) + len(RESET)) + "┐"
        print(top)

        if hi > 0.3:
            hi_color = RED
        elif hi > 0.1:
            hi_color = YELLOW
        else:
            hi_color = GREEN
        print(f"│ {_c(f'⚠  {len(grounded)}/{num_claims} claims grounded', BOLD)}  "
              f"hallucination: {_c(f'{hi:.0%}', hi_color)}")
        print(f"│")

        if grounded:
            print(f"│ {_c('Grounded:', GREEN)}")
            for c in grounded[:8]:
                claim_text = _trunc(c.get("claim", ""), 56)
                stype = c.get("support_type", "?")
                print(f"│  {_c('✓', GREEN)} \"{claim_text}\" [{stype}]")
                for src in c.get("sources", []):
                    sv = src.get("shapley_value", 0)
                    print(f"│    └── {_c(_short_id(src.get('memory_id', '?')), CYAN)}: "
                          f"{sv:.2f}")

        if hallucinated:
            print(f"│")
            print(f"│ {_c('Hallucinated:', RED)}")
            for c in hallucinated:
                claim_text = _trunc(c.get("claim", ""), 56)
                print(f"│  {_c('✗', RED)} \"{claim_text}\"")

        if dead:
            print(f"│")
            print(f"│ {_c(f'Dead: {len(dead)} memories retrieved but unused', YELLOW)}")

        print("└" + "─" * 60 + "┘")
        print()

    def _resolve_short_txn(self, short: str) -> str | None:
        data = self.api.get("/transactions", limit=50)
        for t in data.get("items", []):
            if t.get("id", "").startswith(short):
                return t["id"]
        print(_c(f"  No transaction matching '{short}'", RED))
        return None

    # ── hallucinations ────────────────────────────────────────────────────

    def cmd_hallucinations(self):
        data = self.api.get("/dashboard/hallucinations", limit=20)
        if not data:
            print(_c("  No CAMA data found. Run the pipeline first.", DIM))
            return

        print(f"\n  {_c('Hallucination Report', BOLD)} — transactions sorted by worst rate\n")

        rows = []
        for t in data:
            tid = _c(_short_id(t.get("transaction_id", "?")), CYAN)
            agent = _c(t.get("agent_id", "?"), MAGENTA)
            hi = t.get("hallucination_index", 0)
            hi_str = _c(f"{hi:.0%}", RED if hi > 0.3 else YELLOW if hi > 0.1 else GREEN)
            q = _trunc(t.get("query", ""), 36)
            ts_str = _ts(t.get("created_at"))
            rows.append([tid, agent, hi_str, q, ts_str])

        _table(["Transaction", "Agent", "Halluc%", "Query", "Time"],
               rows, [12, 22, 8, 36, 18])
        print(f"\n  Tip: run {_c('attribute <id>', BOLD)} for full CAMA breakdown\n")

    # ── dead ──────────────────────────────────────────────────────────────

    def cmd_dead(self):
        data = self.api.get("/dashboard/dead-memories", min_recalls=2, max_attribution=0.15)
        if not data:
            print(_c("  No dead memories found. Your memory store is efficient.", GREEN))
            return

        print(f"\n  {_c('Dead Memories', BOLD)} — recalled often, never contribute\n")

        rows = []
        for m in data:
            mid = _c(_short_id(m.get("memory_id", "?")), CYAN)
            agent = _c(m.get("agent_id", "?"), MAGENTA)
            content = _trunc(m.get("content", ""), 44)
            recalls = str(m.get("retrieval_count", 0))
            mean_attr = f"{m.get('mean_attribution', 0):.4f}"
            rows.append([mid, agent, content, recalls, mean_attr])

        _table(["ID", "Agent", "Content", "Recalls", "Mean Attr"],
               rows, [12, 22, 44, 8, 10])
        print(f"\n  These memories consume context tokens but never score in attribution.")
        print(f"  Run {_c('forget <id>', BOLD)} to clean up.\n")

    # ── stats ─────────────────────────────────────────────────────────────

    def cmd_stats(self):
        data = self.api.get("/dashboard/stats")
        print(f"\n  {_c('CortexOS Stats', BOLD)}")
        print(f"  ────────────────────────────────")
        print(f"  Memories:        {_c(str(data.get('total_memories', 0)), BOLD)}")
        print(f"  Agents:          {_c(str(data.get('total_agents', 0)), BOLD)}")
        print(f"  Transactions:    {_c(str(data.get('total_transactions', 0)), BOLD)}")
        print(f"  Attributions:    {_c(str(data.get('total_attributions', 0)), BOLD)}")
        hi = data.get("avg_hallucination_index", 0)
        hi_color = RED if hi > 0.3 else YELLOW if hi > 0.1 else GREEN
        print(f"  Avg halluc. idx: {_c(f'{hi:.2%}', hi_color)}")
        most = data.get("most_active_agent")
        if most:
            print(f"  Most active:     {_c(most, MAGENTA)}")
        print()

    # ── help ──────────────────────────────────────────────────────────────

    def cmd_help(self):
        print(f"""
  {_c('MEMORY COMMANDS', BOLD)}
    {_c('memories', CYAN)}                         List all memories (paginated)
    {_c('memories --agent', CYAN)} <name>          Filter by agent
    {_c('memories --tag', CYAN)} <tag>             Filter by tag
    {_c('memory', CYAN)} <id>                      Show full detail of one memory
    {_c('store', CYAN)} "content" --agent A --tags a,b   Create a memory
    {_c('forget', CYAN)} <id>                      Delete a memory
    {_c('forget --agent', CYAN)} <name> --all      Delete all for an agent
    {_c('n', CYAN)} / {_c('p', CYAN)}                              Next/prev page

  {_c('SEARCH', BOLD)}
    {_c('recall', CYAN)} "query"                   Semantic search (top 5)
    {_c('recall', CYAN)} "query" --agent A --top 10

  {_c('ATTRIBUTION', BOLD)}
    {_c('attribute', CYAN)}                        Show recent CAMA transactions
    {_c('attribute', CYAN)} <txn_id>               Full CAMA detail for a transaction
    {_c('hallucinations', CYAN)}                   All hallucinated claims (compliance view)
    {_c('dead', CYAN)}                             Memories recalled but never useful

  {_c('AGENTS', BOLD)}
    {_c('agents', CYAN)}                           List all agents with stats
    {_c('agent', CYAN)} <id>                       Detail for one agent

  {_c('STATS', BOLD)}
    {_c('stats', CYAN)}                            Overview: totals + hallucination rate

  {_c('OTHER', BOLD)}
    {_c('help', CYAN)}                             This message
    {_c('exit', CYAN)} / {_c('quit', CYAN)} / Ctrl+C             Exit

  Or just type in plain English — the shell will figure it out.
""")

    # ── Natural language routing ──────────────────────────────────────────

    def route_natural_language(self, line: str):
        """Match natural language to a command using keyword patterns."""
        low = line.lower().strip()

        # "delete all memories for agent X"
        if ("delete" in low or "forget" in low or "remove" in low) and "agent" in low:
            parts = low.split()
            for i, w in enumerate(parts):
                if w == "agent" and i + 1 < len(parts):
                    agent = parts[i + 1]
                    self.cmd_forget(["--agent", agent, "--all"])
                    return
            self.cmd_forget([])
            return

        # "memories for agent X" / "what memories does X have" / "pipeline agent"
        if "memor" in low:
            # Try to extract agent name from various phrasings
            import re as _re
            # "the pipeline agent" / "outreach agent" / "agent arcline-X"
            agent_match = _re.search(
                r'(?:the\s+)?(\w[\w-]*)\s+agent|agent\s+(\w[\w-]*)|for\s+(\w[\w-]*)',
                low,
            )
            if agent_match:
                name = next(g for g in agent_match.groups() if g)
                name = name.strip("?.,!")
                if not name.startswith("arcline-"):
                    name = f"arcline-{name}"
                self.cmd_memories(["--agent", name])
                return
            self.cmd_memories([])
            return

        # hallucinations
        if "hallucin" in low:
            self.cmd_hallucinations()
            return

        # dead/unused
        if "dead" in low or "unused" in low or "never used" in low or "never contribute" in low:
            self.cmd_dead()
            return

        # stats
        if "stats" in low or "how many" in low or "overview" in low or "total" in low:
            self.cmd_stats()
            return

        # agents list
        if low in ("agents", "list agents", "show agents"):
            self.cmd_agents()
            return

        # recall / search / find → semantic search
        if any(low.startswith(w) for w in ("recall ", "search ", "find ")):
            query = low.split(None, 1)[1] if " " in low else ""
            self.cmd_recall([query])
            return

        # Default: treat as recall query
        self.cmd_recall([line])

    # ── Main dispatch ─────────────────────────────────────────────────────

    def dispatch(self, line: str):
        line = line.strip()
        if not line:
            return

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("help", "?"):
            self.cmd_help()
        elif cmd in ("exit", "quit", "q"):
            raise SystemExit
        elif cmd == "memories":
            self.cmd_memories(args)
        elif cmd == "memory" and args:
            self.cmd_memory(args[0])
        elif cmd == "store":
            self.cmd_store(args)
        elif cmd == "forget":
            self.cmd_forget(args)
        elif cmd == "recall":
            self.cmd_recall(args)
        elif cmd == "agents":
            self.cmd_agents()
        elif cmd == "agent" and args:
            self.cmd_agent(args[0])
        elif cmd == "attribute":
            self.cmd_attribute(args)
        elif cmd == "hallucinations":
            self.cmd_hallucinations()
        elif cmd == "dead":
            self.cmd_dead()
        elif cmd == "stats":
            self.cmd_stats()
        elif cmd == "n":
            self.cmd_next_page()
        elif cmd == "p":
            self.cmd_prev_page()
        else:
            # Natural language fallback
            self.route_natural_language(line)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CortexOS Shell — interactive memory explorer")
    parser.add_argument("--url", default=os.getenv("CORTEX_URL", "http://localhost:8000"),
                        help="CortexOS engine URL")
    parser.add_argument("--key", default=os.getenv("CORTEX_API_KEY", ""),
                        help="API key (or set CORTEX_API_KEY)")
    args = parser.parse_args()

    api = CortexAPI(args.url, args.key or None)

    # Connection check
    if not api.healthz():
        print(f"{RED}Cannot connect to CortexOS at {args.url}{RESET}")
        print(f"Make sure the server is running: bash /path/to/cortex/start.sh")
        sys.exit(1)

    print(f"""
{_c('🧠 CortexOS Shell v0.1', BOLD)}
{_c(f'Connected to {args.url}', DIM)}
Type {_c('help', CYAN)} for commands, or just ask a question in plain English.
""")

    shell = CortexShell(api)

    try:
        while True:
            try:
                line = input(f"{_c('cortex', MAGENTA)}> ")
                shell.dispatch(line)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
            except SystemExit:
                break
            except httpx.ConnectError:
                print(_c(f"  Connection lost to {args.url}. Is the server running?", RED))
            except httpx.HTTPStatusError as e:
                print(_c(f"  HTTP {e.response.status_code}: {e.response.text[:200]}", RED))
            except Exception as e:
                print(_c(f"  Error: {e}", RED))
    finally:
        api.close()
        print(_c("\nbye 👋", DIM))


if __name__ == "__main__":
    main()
