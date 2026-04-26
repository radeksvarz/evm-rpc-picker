from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Label, ListItem


class RPCListItem(ListItem):
    DEFAULT_CSS = """
    RPCListItem {
        height: 1;
        padding: 0 1;
    }
    .rpc-row-grid {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 5 12;
        height: 1;
    }
    .privacy-symbol {
        width: 100%;
        text-align: center;
    }
    .latency-label {
        width: 100%;
        text-align: right;
        color: #fab387;
    }
    """

    def __init__(
        self,
        url: str,
        tracking: str = "unspecified",
        source: str = "public",
        is_secret: bool = False,
    ) -> None:
        super().__init__()
        self.url = url
        self.tracking = tracking.lower()
        self.source = source.lower()
        self.is_secret = is_secret
        self.latency: float | None = None
        self.latency_label = Label("--- ms", classes="latency-label")
        self.actual_url: str = url
        self.needs_password: bool = False
        self.rpc_id: str | None = None
        self.note: str = ""
        self.encrypted: bool = False
        self.has_secrets: bool = False

    def compose(self) -> ComposeResult:
        # Final ASCII Privacy symbols with specific prefixes
        if self.tracking == "none":
            privacy_symbol = "[green]#SEC[/green]"
        elif self.tracking == "yes":
            privacy_symbol = "[red]!TRK[/red]"
        elif self.tracking == "limited":
            privacy_symbol = "[yellow]~LIM[/yellow]"
        else:
            privacy_symbol = "[dim]?UNK[/dim]"

        with Container(classes="rpc-row-grid"):
            source_tag = ""
            if self.source == "project":
                source_tag = "[bold #f5c2e7][P][/bold #f5c2e7] "
            elif self.source == "global":
                source_tag = "[bold #89b4fa][G][/bold #89b4fa] "

            lock_icon = " [🔒]" if self.is_secret else ""
            display_url = self.url
            if self.is_secret:
                # Mask secret part if needed, but for now just show the URL
                # In Phase 4 we will handle full masking
                pass

            yield Label(f"{source_tag}{display_url}{lock_icon}", classes="url-label")
            yield Label(privacy_symbol, classes="privacy-symbol")
            yield self.latency_label

    def update_latency(self, latency_ms: float | None) -> None:
        self.latency = latency_ms
        if latency_ms is None:
            self.latency_label.update("[red]ERR[/red]")
        else:
            color = "#00ff00" if latency_ms < 200 else "#ffff00" if latency_ms < 500 else "#ff0000"
            self.latency_label.update(f"[{color}]{latency_ms:.0f} ms[/{color}]")
