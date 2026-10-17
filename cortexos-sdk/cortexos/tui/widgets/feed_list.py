"""FeedList — selectable ListView replacement for EventLog RichLog."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from cortexos.tui.state import EventRecord
from cortexos.tui.widgets.event_log import (
    _format_check,
    _format_gate,
    _format_memory_duplicate,
    _format_memory_write,
    _format_shield,
)


def _format_record(record: EventRecord) -> str:
    if record.type == "check":
        return _format_check(record)
    elif record.type == "gate":
        return _format_gate(record)
    elif record.type == "shield":
        return _format_shield(record)
    elif record.type == "memory_write":
        return _format_memory_write(record)
    elif record.type == "memory_duplicate":
        return _format_memory_duplicate(record)
    return ""


class FeedList(ListView):
    """Selectable feed that maps each row to an EventRecord."""

    class EventSelected(Message):
        """Emitted when the user selects an event row."""
        def __init__(self, record: EventRecord) -> None:
            super().__init__()
            self.record = record

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._records: list[EventRecord] = []
        self._filter_type: str | None = None

    def add_event(self, record: EventRecord) -> None:
        self._records.append(record)
        if self._filter_type and record.type != self._filter_type:
            return
        self._append_item(record)

        # Auto-scroll to bottom unless user has scrolled up
        try:
            self.scroll_end(animate=False)
        except Exception:
            pass

        # Notify on injection
        if record.type == "shield" and not record.raw.get("safe", True):
            try:
                self.app.notify("\U0001f534 INJECTION BLOCKED", severity="error")
                self.app.bell()
            except Exception:
                pass

        # Notify on high duplicate rate
        if record.type == "memory_duplicate":
            dup_pct = record.duplicate_pct or 0.0
            if dup_pct >= 40:
                try:
                    self.app.notify(
                        f"\u26a0 Memory store {dup_pct:.0f}% duplicates — burning tokens",
                        severity="warning",
                    )
                except Exception:
                    pass

    def _append_item(self, record: EventRecord) -> None:
        line = _format_record(record)
        if not line:
            return
        item = ListItem(Static(line, markup=True))
        item._record = record  # type: ignore[attr-defined]
        self.append(item)

    def set_filter(self, event_type: str | None) -> None:
        self._filter_type = event_type
        # Rebuild visible items from full record list
        self.clear()
        for record in self._records:
            if event_type is None or record.type == event_type:
                self._append_item(record)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        record = getattr(item, "_record", None)
        if record is not None:
            self.post_message(self.EventSelected(record))
