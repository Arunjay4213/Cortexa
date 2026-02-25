"""CortexOS TUI — Full terminal UI built with Textual.

7 screens: Dashboard, Agent Detail, Transaction, Memories, Hallucinations, Search, Dead.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from cortex_cli.api import CortexAPI
from cortex_cli.config import CORTEX_API_KEY, CORTEX_URL


# ── Helpers ──────────────────────────────────────────────────────

def _sid(s: str) -> str:
    return s[:12] if s else "?"


def _trunc(s: str, n: int = 60) -> str:
    return (s or "").replace("\n", " ").strip()[:n]


def _bar(score: float, w: int = 20) -> str:
    filled = max(0, min(w, int(score * w)))
    return "\u2588" * filled + "\u2591" * (w - filled)


def _bar_rich(score: float, w: int = 20) -> Text:
    filled = max(0, min(w, int(score * w)))
    empty = w - filled
    if score >= 0.7:
        color = "green"
    elif score >= 0.3:
        color = "yellow"
    else:
        color = "red"
    t = Text()
    t.append("\u2588" * filled, style=color)
    t.append("\u2591" * empty, style="dim")
    return t


def _halluc_bar(rate: float, w: int = 15) -> Text:
    filled = max(0, min(w, int(rate * w)))
    empty = w - filled
    t = Text()
    t.append("\u2588" * filled, style="bold red")
    t.append("\u2591" * empty, style="dim")
    return t


def _halluc_style(rate: float) -> str:
    if rate > 0.30:
        return "bold red"
    elif rate > 0.0:
        return "yellow"
    return "green"


def _reason(r: str) -> str:
    return {
        "numerical_ungrounded": "NUM_UNGROUNDED",
        "nli_empty": "NLI_EMPTY",
        "nli_low": "NLI_LOW",
    }.get(r, r.upper() if r else "NLI_EMPTY")


def _categorize(claim: str) -> str:
    cl = claim.lower()
    if any(w in cl for w in ("$", "dollar", "revenue", "cost", "capex", "lease", "irr", "lcoe")):
        return "Financial"
    if any(w in cl for w in ("welcome", "opportunity", "discuss", "looking forward", "call", "regards")):
        return "Conversational"
    if any(w in cl for w in ("week", "month", "day", "timeline", "deadline", "schedule")):
        return "Timeline"
    if any(w in cl for w in ("%", "percent", "average", "approximately")):
        return "Statistical"
    return "Other"


def _ts_ago(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════
# SCREEN 1: DASHBOARD
# ══════════════════════════════════════════════════════════════════

class DashboardScreen(Screen):
    BINDINGS = [
        Binding("a", "push_agents", "Agents"),
        Binding("m", "push_memories", "Memories"),
        Binding("h", "push_hallucinations", "Hallucinations"),
        Binding("s", "push_search", "Search"),
        Binding("d", "push_dead", "Dead Memories"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="dash-stats", classes="section"),
            Static(id="dash-agents", classes="section"),
            Static(id="dash-activity", classes="section"),
            Static(id="dash-dead", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(15, self.refresh_data)

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        api: CortexAPI = self.app.api
        try:
            stats = await api.stats()
            agents = await api.agents()
            txns = await api.transactions(limit=10)
            halluc_data = await api.hallucinations(limit=5)
        except Exception as e:
            self.query_one("#dash-stats", Static).update(
                Text(f"  Connection error: {e}", style="red")
            )
            return

        # ── Stats header ──
        st = Text()
        st.append("\n  ", style="")
        st.append(f"{stats.total_agents}", style="bold cyan")
        st.append(" agents  ", style="dim")
        st.append(f"{stats.total_memories}", style="bold cyan")
        st.append(" memories  ", style="dim")
        st.append(f"{stats.total_transactions}", style="bold cyan")
        st.append(" transactions\n", style="dim")
        self.query_one("#dash-stats", Static).update(st)

        # ── Agent health table ──
        # Compute per-agent hallucination index from transactions
        agent_halluc: dict[str, list[float]] = {}
        agent_txn_count: dict[str, int] = {}
        for t in txns:
            aid = t.agent_id
            agent_txn_count[aid] = agent_txn_count.get(aid, 0) + 1

        # Get halluc from overview if possible
        try:
            overview = await api.overview()
            for a_data in overview.get("agents", []):
                aid = a_data.get("agent_id", "")
                hi = a_data.get("avg_hallucination_index", 0.0)
                if hi is not None:
                    agent_halluc[aid] = [hi]
        except Exception:
            pass

        at = Text()
        at.append("\n  AGENT HEALTH                             LAST 24H\n", style="bold")
        at.append("  " + "\u2500" * 55 + "\n", style="dim")

        # Sort agents by halluc rate (worst first)
        sorted_agents = sorted(
            agents,
            key=lambda a: max(agent_halluc.get(a.agent_id, [0.0])),
            reverse=True,
        )

        for a in sorted_agents:
            avg_h = max(agent_halluc.get(a.agent_id, [0.0]))
            tc = agent_txn_count.get(a.agent_id, a.total_transactions)
            at.append(f"  {a.agent_id:25s} ", style="magenta")

            # Bar
            bar = _halluc_bar(avg_h, 12)
            at.append_text(bar)
            at.append(f" {avg_h*100:3.0f}% halluc", style=_halluc_style(avg_h))

            if tc > 0:
                at.append(f"   {tc} txns", style="dim")
            elif a.total_memories > 0:
                at.append(f"   {a.total_memories} memories", style="dim")
            at.append("\n")

        self.query_one("#dash-agents", Static).update(at)

        # ── Recent activity ──
        act = Text()
        act.append("\n  RECENT ACTIVITY\n", style="bold")
        if halluc_data:
            for h in halluc_data[:5]:
                ago = _ts_ago(h.get("created_at", ""))
                aid = h.get("agent_id", "?")
                hi = h.get("hallucination_index", 0)
                act.append(f"  {ago:8s} ", style="dim")
                act.append(f"{aid:20s} ", style="magenta")
                if hi > 0:
                    act.append(f"halluc index: {hi:.0%}", style="yellow")
                else:
                    act.append("all claims grounded", style="green")
                act.append("\n")
        else:
            for t in txns[:5]:
                ago = _ts_ago(t.created_at)
                act.append(f"  {ago:8s} ", style="dim")
                act.append(f"{t.agent_id:20s} ", style="magenta")
                act.append(f"{_trunc(t.query, 40)}", style="")
                act.append("\n")

        self.query_one("#dash-activity", Static).update(act)

        # ── Dead memories ──
        try:
            dead = await api.dead_memories()
            if dead:
                dt = Text()
                dt.append(f"\n  {len(dead)} dead memories detected", style="yellow")
                dt.append(" (retrieved but never attributed)\n", style="dim")
                self.query_one("#dash-dead", Static).update(dt)
            else:
                self.query_one("#dash-dead", Static).update("")
        except Exception:
            self.query_one("#dash-dead", Static).update("")

    def action_push_agents(self) -> None:
        self.app.push_screen(AgentListScreen())

    def action_push_memories(self) -> None:
        self.app.push_screen(MemoryBrowserScreen())

    def action_push_hallucinations(self) -> None:
        self.app.push_screen(HallucinationScreen())

    def action_push_search(self) -> None:
        self.app.push_screen(SearchScreen())

    def action_push_dead(self) -> None:
        self.app.push_screen(DeadScreen())

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 2: AGENT LIST → AGENT DETAIL
# ══════════════════════════════════════════════════════════════════

class AgentListScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="agent-header", classes="section"),
            DataTable(id="agent-table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_agents()

    @work(exclusive=True)
    async def load_agents(self) -> None:
        api: CortexAPI = self.app.api
        agents = await api.agents()
        self._agents = {a.agent_id: a for a in agents}

        hdr = Text()
        hdr.append("\n  AGENTS\n", style="bold")
        hdr.append("  Select an agent to view details\n", style="dim")
        self.query_one("#agent-header", Static).update(hdr)

        table = self.query_one("#agent-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Agent", "Memories", "Transactions", "Avg Attr", "Last Active")
        table.cursor_type = "row"

        for a in agents:
            table.add_row(
                Text(a.agent_id, style="magenta"),
                str(a.total_memories),
                str(a.total_transactions),
                f"{a.avg_attribution:.3f}" if a.avg_attribution else "-",
                _ts_ago(a.last_active) or "-",
                key=a.agent_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        agent_id = str(event.row_key.value)
        self.app.push_screen(AgentDetailScreen(agent_id))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


class AgentDetailScreen(Screen):
    BINDINGS = [
        Binding("t", "show_transactions", "Transactions"),
        Binding("m", "show_memories", "Memories"),
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="ad-header", classes="section"),
            Static(id="ad-trend", classes="section"),
            Static(id="ad-memories", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_detail()

    @work(exclusive=True)
    async def load_detail(self) -> None:
        api: CortexAPI = self.app.api
        txns = await api.transactions(agent_id=self.agent_id, limit=20)
        mems, total_mems = await api.memories(agent_id=self.agent_id, limit=10)

        # Header
        hdr = Text()
        hdr.append(f"\n  {self.agent_id}\n", style="bold magenta")
        hdr.append("  " + "\u2500" * 55 + "\n", style="dim")
        hdr.append(f"  Transactions: {len(txns):3d}    Memories: {total_mems}\n", style="")
        self.query_one("#ad-header", Static).update(hdr)

        # Transaction list with hallucination info
        trend = Text()
        trend.append("\n  TRANSACTIONS\n", style="bold")
        if txns:
            for t in txns[:10]:
                trend.append(f"  {_sid(t.id)} ", style="cyan")
                trend.append(f" {_ts_ago(t.created_at):8s} ", style="dim")
                trend.append(f"{_trunc(t.query, 40)}\n", style="")
        else:
            trend.append("  No transactions found\n", style="dim")
        self.query_one("#ad-trend", Static).update(trend)

        # Memories
        mem_text = Text()
        mem_text.append(f"\n  MEMORIES ({total_mems} total)\n", style="bold")
        for m in mems:
            mem_text.append(f"  {_sid(m.id)} ", style="cyan")
            mem_text.append(f"{_trunc(m.content, 55)}\n", style="")
        self.query_one("#ad-memories", Static).update(mem_text)

    def action_show_transactions(self) -> None:
        pass  # TODO: push transaction list for agent

    def action_show_memories(self) -> None:
        self.app.push_screen(MemoryBrowserScreen(self.agent_id))

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 3: TRANSACTION DETAIL (CAMA BREAKDOWN)
# ══════════════════════════════════════════════════════════════════

class TransactionScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, txn_id: str):
        super().__init__()
        self.txn_id = txn_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="tx-header", classes="section"),
            Static(id="tx-grounded", classes="section"),
            Static(id="tx-halluc", classes="section"),
            Static(id="tx-dead", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_cama()

    @work(exclusive=True)
    async def load_cama(self) -> None:
        api: CortexAPI = self.app.api

        hdr = Text()
        hdr.append(f"\n  Transaction {_sid(self.txn_id)}\n", style="bold cyan")
        hdr.append("  Loading CAMA analysis...\n", style="dim")
        self.query_one("#tx-header", Static).update(hdr)

        try:
            data = await api.trigger_cama(self.txn_id)
        except Exception as e:
            hdr.append(f"\n  Error: {e}\n", style="red")
            self.query_one("#tx-header", Static).update(hdr)
            return

        claims = data.get("claims", [])
        grounded = [c for c in claims if not c.get("is_hallucination")]
        hallucinated = [c for c in claims if c.get("is_hallucination")]
        hi = data.get("hallucination_index", 0)
        dead = data.get("dead_memories", [])

        # Header
        hdr = Text()
        hdr.append(f"\n  Transaction {_sid(self.txn_id)}", style="bold cyan")
        hdr.append(f"  {data.get('num_claims', 0)} claims\n", style="dim")
        hdr.append(f"\n  ", style="")
        if hallucinated:
            hdr.append(f"{len(grounded)}/{len(claims)} grounded", style="green")
            hdr.append(f"  {len(hallucinated)} hallucinated", style="red")
            hdr.append(f"  index: {hi:.0%}\n", style=_halluc_style(hi))
        else:
            hdr.append(f"All {len(claims)} claims grounded", style="green")
            hdr.append("\n")
        self.query_one("#tx-header", Static).update(hdr)

        # Grounded claims
        gt = Text()
        if grounded:
            gt.append("\n  GROUNDED CLAIMS\n", style="bold green")
            for c in grounded:
                gt.append("  \u2713 ", style="green")
                gt.append(f"\"{_trunc(c['claim'], 60)}\"", style="")
                gt.append(f" [{c.get('claim_type', '?')}]\n", style="dim")
                for src in c.get("sources", []):
                    sv = src.get("shapley_value", 0)
                    ent = src.get("entailment", 0)
                    gt.append(f"     \u2514\u2500\u2500 {_sid(src['memory_id'])} ", style="cyan")
                    gt.append_text(_bar_rich(sv, 16))
                    gt.append(f" {sv:.2f}", style="bold")
                    gt.append(f" ent={ent:.3f}", style="dim")
                    gt.append(f" {c.get('support_type', '')}\n", style="dim")
        self.query_one("#tx-grounded", Static).update(gt)

        # Hallucinated claims
        ht = Text()
        if hallucinated:
            ht.append("\n  HALLUCINATED CLAIMS\n", style="bold red")
            for c in hallucinated:
                reason = c.get("hallucination_reason", "") or "nli_empty"
                ht.append("  \u2717 ", style="red")
                ht.append(f"\"{_trunc(c['claim'], 55)}\"", style="")
                ht.append(f" [{_reason(reason)}]\n", style="yellow")
        self.query_one("#tx-halluc", Static).update(ht)

        # Dead memories
        dt = Text()
        if dead:
            dt.append(f"\n  DEAD MEMORIES ({len(dead)} retrieved but unused)\n", style="bold yellow")
            for mid in dead:
                dt.append(f"  \u2022 {_sid(mid)}\n", style="dim")
        self.query_one("#tx-dead", Static).update(dt)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 4: MEMORY BROWSER
# ══════════════════════════════════════════════════════════════════

class MemoryBrowserScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("n", "next_page", "Next"),
        Binding("p", "prev_page", "Prev"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, agent_id: str | None = None):
        super().__init__()
        self.agent_id = agent_id
        self._page = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="mem-header", classes="section"),
            DataTable(id="mem-table"),
            Static(id="mem-footer-info", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_memories()

    @work(exclusive=True)
    async def load_memories(self) -> None:
        api: CortexAPI = self.app.api
        mems, total = await api.memories(
            agent_id=self.agent_id, limit=20, offset=self._page * 20,
        )

        hdr = Text()
        if self.agent_id:
            hdr.append(f"\n  Memories for {self.agent_id}", style="bold magenta")
        else:
            hdr.append("\n  All Memories", style="bold")
        hdr.append(f"  ({total} total, page {self._page + 1})\n", style="dim")
        self.query_one("#mem-header", Static).update(hdr)

        table = self.query_one("#mem-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Agent", "Content", "Recalls", "Created")
        table.cursor_type = "row"

        for m in mems:
            table.add_row(
                Text(_sid(m.id), style="cyan"),
                Text(m.agent_id, style="magenta"),
                _trunc(m.content, 50),
                str(m.retrieval_count),
                _ts_ago(m.created_at) or "-",
                key=m.id,
            )

    def action_next_page(self) -> None:
        self._page += 1
        self.load_memories()

    def action_prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self.load_memories()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 5: HALLUCINATION REPORT
# ══════════════════════════════════════════════════════════════════

class HallucinationScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="hall-header", classes="section"),
            Static(id="hall-agents", classes="section"),
            Static(id="hall-categories", classes="section"),
            Static(id="hall-worst", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_data()

    @work(exclusive=True)
    async def load_data(self) -> None:
        api: CortexAPI = self.app.api
        halluc_list = await api.hallucinations(limit=50)
        txns = await api.transactions(limit=50)

        # Group by agent
        agent_halluc: dict[str, list[float]] = {}
        total_halluc_claims = 0
        all_halluc_claims: list[dict] = []

        for h in halluc_list:
            aid = h.get("agent_id", "?")
            hi = h.get("hallucination_index", 0)
            if aid not in agent_halluc:
                agent_halluc[aid] = []
            agent_halluc[aid].append(hi)

        # Try to get detailed claims from recent transactions
        for t in txns[:10]:
            try:
                cama = await api.trigger_cama(t.id)
                for c in cama.get("claims", []):
                    if c.get("is_hallucination"):
                        total_halluc_claims += 1
                        all_halluc_claims.append({
                            "claim": c["claim"],
                            "agent": t.agent_id,
                            "reason": c.get("hallucination_reason", ""),
                            "txn": t.id,
                        })
            except Exception:
                pass

        # Header
        hdr = Text()
        hdr.append("\n  HALLUCINATION REPORT\n", style="bold red")
        hdr.append(f"  {total_halluc_claims} hallucinated claims", style="")
        hdr.append(f" across {len(halluc_list)} transactions\n", style="dim")
        self.query_one("#hall-header", Static).update(hdr)

        # By agent
        at = Text()
        at.append("\n  BY AGENT (worst first)\n", style="bold")
        at.append("  " + "\u2500" * 55 + "\n", style="dim")
        sorted_agents = sorted(
            agent_halluc.items(),
            key=lambda kv: sum(kv[1]) / len(kv[1]) if kv[1] else 0,
            reverse=True,
        )
        for aid, rates in sorted_agents:
            avg = sum(rates) / len(rates) if rates else 0
            at.append(f"  {aid:25s} ", style="magenta")
            at.append_text(_halluc_bar(avg, 15))
            at.append(f" {avg:.0%} avg", style=_halluc_style(avg))
            at.append(f"  ({len(rates)} txns)\n", style="dim")
        self.query_one("#hall-agents", Static).update(at)

        # By category
        categories = Counter(_categorize(c["claim"]) for c in all_halluc_claims)
        ct = Text()
        if categories:
            ct.append("\n  BY CATEGORY\n", style="bold")
            ct.append("  " + "\u2500" * 55 + "\n", style="dim")
            cat_icons = {
                "Financial": "$", "Conversational": ">",
                "Timeline": "@", "Statistical": "#", "Other": "?",
            }
            for cat, count in categories.most_common():
                icon = cat_icons.get(cat, "?")
                ct.append(f"  {icon} {cat:25s}", style="yellow")
                ct.append(f" {count} claims\n", style="")
        self.query_one("#hall-categories", Static).update(ct)

        # Worst offenders
        wt = Text()
        if all_halluc_claims:
            wt.append("\n  RECENT HALLUCINATED CLAIMS\n", style="bold")
            for c in all_halluc_claims[:8]:
                reason = _reason(c["reason"])
                wt.append(f"  [{reason:16s}] ", style="yellow")
                wt.append(f"{_trunc(c['claim'], 50)}\n", style="")
        self.query_one("#hall-worst", Static).update(wt)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 6: SEARCH
# ══════════════════════════════════════════════════════════════════

class SearchScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static("\n  SEMANTIC SEARCH\n", classes="section"),
            Input(placeholder="Type a query and press Enter...", id="search-input"),
            VerticalScroll(
                Static(id="search-results", classes="section"),
            ),
        )
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query:
            self.run_search(query)

    @work(exclusive=True)
    async def run_search(self, query: str) -> None:
        api: CortexAPI = self.app.api
        results = await api.search(query, top_k=10)

        rt = Text()
        rt.append(f"\n  {len(results)} results for \"{query}\"\n\n", style="bold")

        for r in results:
            mem = r.get("memory", {})
            sim = r.get("similarity", 0)
            rt.append(f"  {sim:.2f} ", style="bold")
            rt.append_text(_bar_rich(sim, 16))
            rt.append(f"  {mem.get('agent_id', '?')}\n", style="magenta")
            rt.append(f"  \"{_trunc(mem.get('content', ''), 65)}\"\n\n", style="")

        self.query_one("#search-results", Static).update(rt)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# SCREEN 7: DEAD MEMORIES
# ══════════════════════════════════════════════════════════════════

class DeadScreen(Screen):
    BINDINGS = [
        Binding("b", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(
            Static(id="dead-header", classes="section"),
            Static(id="dead-list", classes="section"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.load_dead()

    @work(exclusive=True)
    async def load_dead(self) -> None:
        api: CortexAPI = self.app.api
        try:
            dead = await api.dead_memories()
        except Exception as e:
            self.query_one("#dead-header", Static).update(
                Text(f"\n  Error loading dead memories: {e}\n", style="red")
            )
            return

        hdr = Text()
        hdr.append("\n  DEAD MEMORIES\n", style="bold yellow")
        hdr.append(f"  {len(dead)} memories retrieved but NEVER attributed\n", style="")
        hdr.append("  These waste recall slots and tokens.\n", style="dim")
        self.query_one("#dead-header", Static).update(hdr)

        lt = Text()
        for d in dead:
            lt.append(f"\n  {_sid(d.memory_id)} ", style="cyan")
            lt.append(f"{d.agent_id}\n", style="magenta")
            lt.append(f"  \"{_trunc(d.content, 60)}\"\n", style="")
            lt.append(f"  Recalled: {d.retrieval_count}x  ", style="dim")
            lt.append(f"Avg attr: {d.mean_attribution:.3f}\n", style="dim")

        if not dead:
            lt.append("\n  No dead memories found. All memories are contributing.\n", style="green")

        self.query_one("#dead-list", Static).update(lt)

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


# ══════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════

class CortexApp(App):
    """CortexOS Terminal UI."""

    TITLE = "CortexOS"
    SUB_TITLE = "Memory Attribution Engine"
    CSS = """
    Screen {
        background: $surface;
    }
    .section {
        margin: 0 1;
    }
    #search-input {
        margin: 0 2;
    }
    DataTable {
        margin: 0 1;
        height: auto;
        max-height: 30;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, url: str | None = None, key: str | None = None):
        super().__init__()
        self.api = CortexAPI(
            base_url=url or CORTEX_URL,
            api_key=key or CORTEX_API_KEY,
        )

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())

    async def action_quit(self) -> None:
        await self.api.close()
        self.exit()
