"""Sortable/filterable DataTable for claims with full color coding."""

from __future__ import annotations

from textual.widgets import DataTable

from cortexos.tui.helpers import conf_color, verdict_icon
from cortexos.tui.state import EventRecord

_COLUMNS = ("#", "Time", "Verdict", "Conf", "Claim Text")


def _verdict_display(verdict: str) -> str:
    """Format verdict with icon and color for table cell."""
    icon, color = verdict_icon(verdict)
    v = verdict.upper()
    if v == "GROUNDED":
        return f"[{color}]{icon} GROUNDED    [/]"
    elif v == "NUM_MISMATCH":
        return f"[{color}]{icon} NUM_MISMATCH[/]"
    elif v == "UNSUPPORTED":
        return f"[{color}]{icon} UNSUPPORTED [/]"
    elif v == "OPINION":
        return f"[{color}]{icon} OPINION     [/]"
    return f"[#555555]? {verdict}[/]"


class ClaimTable(DataTable):
    """DataTable showing all claims across checks with rich formatting."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._claims: list[tuple[EventRecord, dict]] = []
        self._filter_verdict: str | None = None
        self._search_text: str = ""
        self._sort_key: str = "time"
        self._sort_reverse: bool = True
        self._counter: int = 0

    def on_mount(self) -> None:
        self.cursor_type = "row"
        for col in _COLUMNS:
            self.add_column(col, key=col)

    def add_claim(self, event: EventRecord, claim: dict) -> None:
        self._counter += 1
        self._claims.append((event, claim))
        if self._matches(event, claim):
            self._add_row(self._counter, event, claim)
            self.scroll_end()

    def _matches(self, event: EventRecord, claim: dict) -> bool:
        verdict = claim.get("verdict", "")
        if self._filter_verdict and verdict != self._filter_verdict:
            return False
        if self._search_text and self._search_text.lower() not in claim.get("text", "").lower():
            return False
        return True

    def _add_row(self, idx: int, event: EventRecord, claim: dict) -> None:
        time_str = event.ts.strftime("%H:%M:%S")
        verdict = claim.get("verdict", "?")
        verdict_str = _verdict_display(verdict)
        conf = claim.get("confidence", 0.0)
        color = conf_color(conf)
        conf_str = f"[{color}]{conf:.2f}[/]"
        text = claim.get("text", "")
        if len(text) > 50:
            text = text[:47] + "..."
        self.add_row(
            str(idx).zfill(3), time_str, verdict_str, conf_str, text,
            key=f"claim-{idx}",
        )

    def filter_by_verdict(self, verdict: str | None) -> None:
        self._filter_verdict = verdict
        self._rebuild()

    def search(self, text: str) -> None:
        self._search_text = text
        self._rebuild()

    def sort_by(self, key: str) -> None:
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = key
            self._sort_reverse = True
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear()
        filtered = [
            (i + 1, e, c)
            for i, (e, c) in enumerate(self._claims)
            if self._matches(e, c)
        ]
        if self._sort_key == "verdict":
            filtered.sort(key=lambda x: x[2].get("verdict", ""), reverse=self._sort_reverse)
        elif self._sort_key == "confidence":
            filtered.sort(key=lambda x: x[2].get("confidence", 0.0), reverse=self._sort_reverse)
        elif self._sort_reverse:
            filtered.reverse()

        for idx, event, claim in filtered:
            self._add_row(idx, event, claim)
