"""Tab 2: Claims — Sortable, filterable live claims table."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TabPane

from cortexos.tui.state import EventRecord, SessionState
from cortexos.tui.widgets.claim_table import ClaimTable

_VERDICT_CYCLE = [None, "GROUNDED", "NUM_MISMATCH", "UNSUPPORTED", "OPINION"]


class ClaimsTab(TabPane):
    """Live table of ALL claims across all checks."""

    BINDINGS = [
        ("s", "sort_cycle", "Sort"),
        ("f", "filter_verdict", "Filter"),
    ]

    def __init__(self, state: SessionState, **kwargs) -> None:
        super().__init__("CLAIMS", id="tab-claims", **kwargs)
        self._state = state
        self._verdict_idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="claims-pane"):
            yield ClaimTable(id="claims-table")
            yield Static(
                "[#00FF88][enter][/] [#444444]full detail[/]  "
                "[#00FF88][s][/] [#444444]sort[/]  "
                "[#00FF88][/][/] [#444444]search[/]  "
                "[#00FF88][f][/] [#444444]filter[/]",
                id="claims-footer",
            )

    def add_event(self, record: EventRecord) -> None:
        table = self.query_one("#claims-table", ClaimTable)
        for claim in record.claims:
            table.add_claim(record, claim)

    def on_data_table_row_selected(self, event: ClaimTable.RowSelected) -> None:
        """Navigate to inspect tab when a claim row is selected."""
        # Find the event for this claim
        row_key = event.row_key
        if row_key and str(row_key.value).startswith("claim-"):
            idx = int(str(row_key.value).split("-")[1]) - 1
            if 0 <= idx < len(self._state.events):
                # Find the event that contains this claim
                claims = self._state.all_claims()
                if idx < len(claims):
                    record, _ = claims[idx]
                    self.app.inspect_event(record)

    def action_sort_cycle(self) -> None:
        table = self.query_one("#claims-table", ClaimTable)
        cycle = ["time", "verdict", "confidence"]
        try:
            idx = cycle.index(table._sort_key)
        except ValueError:
            idx = -1
        next_key = cycle[(idx + 1) % len(cycle)]
        table.sort_by(next_key)
        self.notify(f"Sort: {next_key}")

    def action_filter_verdict(self) -> None:
        self._verdict_idx = (self._verdict_idx + 1) % len(_VERDICT_CYCLE)
        verdict = _VERDICT_CYCLE[self._verdict_idx]
        table = self.query_one("#claims-table", ClaimTable)
        table.filter_by_verdict(verdict)
        self.notify(f"Filter: {verdict or 'all'}")
