from typing import Optional
from textual.containers import Horizontal
from textual.widgets import Label, ListItem

class RPCListItem(ListItem):
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.latency: Optional[float] = None
        self.latency_label = Label("--- ms", classes="latency-label")

    def compose(self):
        with Horizontal():
            yield Label(self.url, classes="url-label")
            yield self.latency_label

    def update_latency(self, latency_ms: Optional[float]) -> None:
        self.latency = latency_ms
        if latency_ms is None:
            self.latency_label.update("[red]ERR[/red]")
        else:
            color = "#00ff00" if latency_ms < 200 else "#ffff00" if latency_ms < 500 else "#ff0000"
            self.latency_label.update(f"[{color}]{latency_ms:.0f} ms[/{color}]")
