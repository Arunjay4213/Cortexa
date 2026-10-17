"""HI trend sparkline widget using block characters."""

from __future__ import annotations

from textual.widgets import Static

from cortexos.tui.helpers import sparkline


class HISparkline(Static):
    """Displays last 30 HI values as a colored block-char sparkline."""

    def __init__(self, **kwargs) -> None:
        super().__init__("[#333333]no data[/]", **kwargs)
        self._values: list[float] = []

    def update_values(self, values: list[float]) -> None:
        self._values = values[-30:]
        if not self._values:
            self.update("[#333333]no data[/]")
        else:
            line = sparkline(self._values)
            self.update(f"[#333333]0.0[/] {line} [#333333]1.0[/]")
