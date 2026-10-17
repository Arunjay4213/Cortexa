"""Tab 5: Inspect — Full detail view for a selected event."""

from __future__ import annotations

import json
import os
import tempfile

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import RichLog, Static, TabPane

from cortexos.tui.helpers import conf_color, hi_color, verdict_icon
from cortexos.tui.state import EventRecord


class InspectTab(TabPane):
    """Full detail on a selected event with claims and Shapley attribution."""

    BINDINGS = [
        ("e", "export_json", "Export"),
        ("r", "re_verify", "Re-verify"),
        ("t", "show_trace_cmd", "Trace"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__("INSPECT", id="tab-inspect", **kwargs)
        self._record: EventRecord | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="inspect-pane"):
            yield Static(
                "[#444444]Select an event from FEED or CLAIMS to inspect[/]",
                id="inspect-empty",
            )
            yield Static("", id="inspect-header-bar")
            yield Static("CLAIMS", id="inspect-claims-title")
            with VerticalScroll(id="inspect-claims-section"):
                yield RichLog(highlight=False, markup=True, wrap=True, id="inspect-claims-log")
            with VerticalScroll(id="inspect-trace-section"):
                yield RichLog(highlight=False, markup=True, wrap=True, id="inspect-trace-log")
            yield Static(
                "[#00FF88][e][/] [#444444]export JSON[/]  "
                "[#00FF88][r][/] [#444444]re-verify[/]  "
                "[#00FF88][t][/] [#444444]trace[/]",
                id="inspect-actions",
            )

    def on_mount(self) -> None:
        self.query_one("#inspect-header-bar").display = False
        self.query_one("#inspect-claims-title").display = False
        self.query_one("#inspect-claims-section").display = False
        self.query_one("#inspect-actions").display = False
        self.query_one("#inspect-trace-section").display = False

    def show_event(self, record: EventRecord) -> None:
        self._record = record

        # Show detail sections, hide empty placeholder
        self.query_one("#inspect-empty").display = False
        self.query_one("#inspect-header-bar").display = True
        self.query_one("#inspect-claims-title").display = True
        self.query_one("#inspect-claims-section").display = True
        self.query_one("#inspect-actions").display = True

        # Header bar
        header = self.query_one("#inspect-header-bar", Static)
        hi_c = hi_color(record.hi)
        h_count = record.hallucinated
        t_count = record.total_claims
        agent_label = record.agent_id if record.agent_id != "unknown" else ""
        agent_str = f"  [#AA44FF]{agent_label}[/]" if agent_label else ""
        header.update(
            f"[#DDDDDD]{record.type.upper()} #{len(self.app.state.events):03d}[/]  "
            f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]  "
            f"[#00DDFF]{record.latency_ms:.0f}ms[/]  "
            f"[{hi_c}]\u25cf HI:{record.hi:.2f}[/]  "
            f"[#FFFFFF]{h_count}/{t_count} hallucinated[/]"
            f"{agent_str}"
        )

        # Build everything into a single RichLog
        claims_log = self.query_one("#inspect-claims-log", RichLog)
        claims_log.clear()

        if not record.claims:
            claims_log.write("[#444444]No claims data available.[/]")
            return

        has_attribution = False

        # ── Section 1: Claims ──────────────────────────────────
        claims_log.write(f"[bold #00DDFF]\u25a6 CLAIMS[/]  [#333333]{len(record.claims)} extracted[/]")
        claims_log.write(f"[#333333]{'─' * 50}[/]")
        claims_log.write("")

        for i, claim in enumerate(record.claims, 1):
            verdict = claim.get("verdict", "?")
            grounded = claim.get("grounded", False)
            conf = claim.get("confidence", 0.0)
            text = claim.get("text", "")
            reason = claim.get("reason", "")
            quote = claim.get("source_quote", "")
            attribution = claim.get("attribution")

            icon_char, icon_color = verdict_icon(verdict)

            claims_log.write(
                f"  [{icon_color}]{icon_char}[/]  "
                f"[{icon_color}]{verdict:14}[/]  "
                f"'{text}'"
            )

            # Confidence bar
            bar_color = "#00FF88" if grounded else "#FF3366"
            bar_fill = int(conf * 16)
            bar_empty = 16 - bar_fill
            conf_c = conf_color(conf)
            fill = "\u2588"
            empty = "\u2591"
            conf_bar = f"[{bar_color}]{fill * bar_fill}[/][dim]{empty * bar_empty}[/]"
            claims_log.write(
                f"         [#555555]conf:[/] [{conf_c}]{conf:.2f}[/]  {conf_bar}"
            )

            if quote:
                claims_log.write(f"         [#666666]\u25b8 \"{quote[:100]}\"[/]")
            elif reason:
                claims_log.write(f"         [#666666]\u25b8 {reason[:100]}[/]")

            if attribution:
                has_attribution = True

            claims_log.write("")

        # ── Section 2: Shapley Attribution ─────────────────────
        attributed_claims = [
            c for c in record.claims
            if c.get("attribution") and len(c["attribution"]) > 0
        ]

        if attributed_claims:
            claims_log.write("")
            claims_log.write("[bold #AA44FF]\u25c8 SHAPLEY ATTRIBUTION[/]  [#333333]source influence scores[/]")
            claims_log.write(f"[#333333]{'─' * 50}[/]")

            for claim in attributed_claims:
                attr = claim["attribution"]
                text = claim.get("text", "")[:60]
                grounded = claim.get("grounded", False)
                icon = "\u2726" if grounded else "\u25cf"
                color = "#00FF88" if grounded else "#FF3366"

                claims_log.write(f"  [{color}]{icon}[/] '{text}'")

                # Show top 3 influences
                influences = attr[:3] if isinstance(attr, list) else []
                for inf in influences:
                    phi = inf.get("influence", 0.0)
                    direction = inf.get("direction", "IRRELEVANT")
                    src_idx = inf.get("source_index", 0)
                    preview = inf.get("source_preview", "")[:70]

                    if direction == "SUPPORTS":
                        dir_color = "#00FF88"
                    elif direction == "CONTRADICTS":
                        dir_color = "#FF3366"
                    else:
                        dir_color = "#555555"

                    # Influence bar (24 chars)
                    bar_fill = round(abs(phi) * 24)
                    bar_empty = 24 - bar_fill
                    fill = "\u2588"
                    empty = "\u2591"
                    inf_bar = f"[#AA44FF]{fill * bar_fill}[/][dim]{empty * bar_empty}[/]"

                    claims_log.write(
                        f"    \u2192 src[{src_idx}]  "
                        f"[#AA44FF]\u03c6={phi:.2f}[/]  "
                        f"[{dir_color}]\u25cf {direction}[/]"
                    )
                    claims_log.write(f"      {inf_bar}")
                    if preview:
                        claims_log.write(f"      [#666666]{preview}[/]")

                claims_log.write("")
        # Attribution always-on — no fallback message needed

        # ── Section 3: Root Cause Diagnosis ────────────────────
        hallucinated = [c for c in record.claims if not c.get("grounded", True)]
        if hallucinated:
            claims_log.write("")
            claims_log.write("[bold #FF3366]\u26a0 ROOT CAUSE DIAGNOSIS[/]  [#333333]why claims failed[/]")
            claims_log.write(f"[#333333]{'─' * 50}[/]")

            for claim in hallucinated:
                text = claim.get("text", "")[:60]
                claims_log.write(f"  [#FF3366]\u2717 '{text}'[/]")

                attr = claim.get("attribution")
                if attr and isinstance(attr, list):
                    contradicting = [
                        a for a in attr if a.get("direction") == "CONTRADICTS"
                    ]
                    if contradicting:
                        top = contradicting[0]
                        claims_log.write(
                            f"    [#AA44FF]Caused by:[/] "
                            f"src[{top.get('source_index', 0)}] "
                            f"(\u03c6={top.get('influence', 0):.2f})"
                        )
                        preview = top.get("source_preview", "")[:70]
                        if preview:
                            claims_log.write(
                                f"    [#666666]Source says: '{preview}'[/]"
                            )
                    else:
                        claims_log.write(
                            f"    [#666666]No source supports this claim \u2014 fabricated[/]"
                        )
                else:
                    verdict = claim.get("verdict", "")
                    reason = claim.get("reason", "")
                    if reason:
                        claims_log.write(f"    [#666666]{verdict}: {reason[:80]}[/]")
                    else:
                        claims_log.write(
                            f"    [#666666]No attribution data available[/]"
                        )

                claims_log.write("")

    def action_export_json(self) -> None:
        if not self._record:
            self.notify("No event selected", severity="warning")
            return
        path = os.path.join(tempfile.gettempdir(), "cortex_event.json")
        with open(path, "w") as f:
            json.dump(self._record.raw, f, indent=2, default=str)
        self.notify(f"Exported to {path}")

    def action_re_verify(self) -> None:
        if not self._record:
            self.notify("No event selected", severity="warning")
            return
        import asyncio
        asyncio.create_task(self._do_re_verify())

    async def _do_re_verify(self) -> None:
        import httpx
        record = self._record
        if not record:
            return

        # Build request from the raw event data
        sources = record.raw.get("sources", [])
        response_text = record.response_preview
        if not response_text:
            self.notify("No response text to re-verify", severity="warning")
            return

        app = self.app
        headers = {"Content-Type": "application/json"}
        if hasattr(app, "api_key") and app.api_key:
            headers["Authorization"] = f"Bearer {app.api_key}"
        base = app.base_url.rstrip("/") if hasattr(app, "base_url") else ""

        self.notify("Re-verifying with attribution...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "response": response_text,
                    "sources": sources,
                    "agent_id": record.agent_id,
                    "config": {"attribution": True, "attribution_threshold": 0.05},
                }
                resp = await client.post(f"{base}/v1/check", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Reconstruct a synthetic EventRecord from the fresh result
            from cortexos.tui.state import EventRecord
            from datetime import datetime, timezone
            synth_data = {
                "type": "check",
                "ts": datetime.now(timezone.utc).isoformat(),
                "hi": data.get("hallucination_index", 0.0),
                "total_claims": data.get("total_claims", 0),
                "grounded": data.get("grounded_count", 0),
                "hallucinated": data.get("hallucinated_count", 0),
                "opinion_count": data.get("opinion_count", 0),
                "latency_ms": data.get("latency_ms", 0.0),
                "claims": [
                    {
                        "text": c.get("text", ""),
                        "verdict": c.get("verdict", ""),
                        "grounded": c.get("grounded", False),
                        "confidence": c.get("confidence", 0.0),
                        "source_quote": c.get("source_quote"),
                        "reason": c.get("reason"),
                        "attribution": c.get("attribution"),
                    }
                    for c in data.get("claims", [])
                ],
                "verdicts": [c.get("verdict", "") for c in data.get("claims", [])],
                "agent_id": record.agent_id,
                "api_key_id": record.api_key_id,
                "response_preview": response_text[:200],
                "flagged": data.get("hallucinated_count", 0),
                "flagged_claims": [],
                "sources": sources,
            }
            new_record = EventRecord.from_sse(synth_data)
            if new_record:
                self.show_event(new_record)
                self.notify(f"Re-verified: HI={new_record.hi:.2f}")
        except Exception as e:
            self.notify(f"Re-verify failed: {e}", severity="error")

    def show_trace(self, trace_data: dict) -> None:
        """Display trace results in the trace section."""
        trace_log = self.query_one("#inspect-trace-log", RichLog)
        trace_section = self.query_one("#inspect-trace-section")
        trace_section.display = True
        trace_log.clear()

        matches = trace_data.get("matches", [])
        trace_log.write("[bold #AA44FF]\u25c8 MEMORY TRACE[/]")
        trace_log.write(f"[#222222]{'─' * 50}[/]")

        if not matches:
            trace_log.write("[#444444]No matching memories found[/]")
            return

        for i, m in enumerate(matches[:5], 1):
            score = m.get("relevance_score", 0.0)
            text = m.get("memory_text", "")[:120]
            mem_id = m.get("memory_id", "")[:12]
            if score >= 0.7:
                score_color = "#00FF88"
            elif score >= 0.4:
                score_color = "#F5A623"
            else:
                score_color = "#555555"
            trace_log.write(
                f"  [#444444]{i}.[/]  [{score_color}]\u03c6={score:.2f}[/]  "
                f"[#777777]{mem_id}[/]"
            )
            trace_log.write(f"     [#AAAAAA]{text}[/]")
            trace_log.write("")

    def action_show_trace_cmd(self) -> None:
        if not self._record:
            self.notify("No event selected — use :trace <query> from command palette", severity="warning")
            return
        # Run trace using the response preview as the query
        query = self._record.response_preview[:200]
        if not query:
            self.notify("No text to trace", severity="warning")
            return
        import asyncio
        asyncio.create_task(self._do_trace(query))

    async def _do_trace(self, query: str) -> None:
        import httpx
        app = self.app
        headers = {"Content-Type": "application/json"}
        if hasattr(app, "api_key") and app.api_key:
            headers["Authorization"] = f"Bearer {app.api_key}"
        base = app.base_url.rstrip("/") if hasattr(app, "base_url") else ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"query": query, "agent_id": "tui-cmd", "top_k": 5}
                resp = await client.post(f"{base}/v1/memory/trace", json=payload, headers=headers)
                data = resp.json()
            self.show_trace(data)
            matches = data.get("matches", [])
            self.notify(f"Trace: {len(matches)} memory match(es) found")
        except Exception as e:
            self.notify(f"Trace failed: {e}", severity="error")
