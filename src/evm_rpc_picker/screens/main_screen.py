from typing import Any, Dict, List

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label

from ..models import fetch_chains, get_cached_chains
from ..widgets import ChainsTable, SearchInput
from .rpc_screen import RPCScreen


class MainScreen(Screen[str]):
    """Main screen for searching and listing chains."""

    DEFAULT_CSS = """
    #search-container {
        height: auto;
        padding: 1 2;
        background: #181825;
        align: left middle;
    }

    #search-input {
        width: 1fr;
        border: solid #313244;
        background: #1e1e2e;
        color: #cdd6f4;
    }

    #filter-status {
        width: 18;
        margin-left: 2;
        background: #313244;
        color: #f5c2e7;
        text-style: bold;
        text-align: center;
        border: solid #45475a;
        content-align: center middle;
        height: 3;
    }

    #search-input:focus {
        border: solid #89b4fa;
    }

    #list-container {
        padding: 0 2;
    }

    DataTable {
        height: 1fr;
        border: solid #313244;
        background: #1e1e2e;
        color: #cdd6f4;
    }

    DataTable:focus {
        border: solid #89b4fa;
    }

    DataTable > .datatable--cursor {
        background: #89b4fa 30%;
    }

    DataTable > .datatable--header {
        background: #313244;
        color: #f5e0dc;
        text-style: bold;
    }

    #env-status-container {
        background: #181825;
        height: 1;
        width: 100%;
        padding: 0 2;
    }

    #env-status {
        color: #9399b2;
        width: 1fr;
        height: 1;
        text-style: italic;
    }

    #env-latency {
        width: 10;
        text-align: right;
    }

    #env-status:focus {
        background: #313244;
        color: #f5c2e7;
        text-style: bold italic;
    }
    """

    BINDINGS = [
        ("enter", "submit", "Select"),
        ("tab", "focus_next", "Switch Focus"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "load_data", "Refresh Data"),
        ("ctrl+t", "toggle_filter", "Toggle Filter"),
    ]

    def __init__(self):
        super().__init__()
        self.chains: List[Dict[str, Any]] = []
        self.filtered_chains: List[Dict[str, Any]] = []
        self.filter_mode: str = "all"  # all, mainnet, testnet
        self.current_env_rpc: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="search-container"):
            yield SearchInput(placeholder="Search by name or chain ID (e.g. Ethereum, 1, Polygon...)", id="search-input")
            yield Label("Filter: ALL", id="filter-status")
        with Container(id="list-container"):
            table = ChainsTable(id="chain-table")
            table.can_focus = True
            yield table
        with Horizontal(id="env-status-container"):
            env_label = Label(id="env-status")
            env_label.can_focus = True
            yield env_label
            yield Label("--- ms", id="env-latency")
        yield Footer()

    async def on_mount(self) -> None:
        import os
        self.current_env_rpc = os.environ.get("ETH_RPC_URL")
        display_rpc = self.current_env_rpc or "not set"
        self.query_one("#env-status", Label).update(f" Current ETH_RPC_URL: [bold #89b4fa]{display_rpc}[/bold #89b4fa]")
        
        if self.current_env_rpc:
            self.run_worker(self.check_system_latency())
            
        table = self.query_one(ChainsTable)
        table.add_columns("Chain Name", "ID", "Currency")
        table.cursor_type = "row"
        self.update_filter_status()
        self.query_one(SearchInput).focus()
        self.run_worker(self.load_data())

    def update_filter_status(self) -> None:
        mode_label = self.filter_mode.upper()
        try:
            self.query_one("#filter-status", Label).update(f"Filter: {mode_label}")
        except Exception:
            pass

    def action_load_data(self) -> None:
        self.run_worker(self.load_data())

    def action_toggle_filter(self) -> None:
        modes = ["all", "mainnet", "testnet"]
        current_idx = modes.index(self.filter_mode)
        self.filter_mode = modes[(current_idx + 1) % len(modes)]
        
        # Update UI
        self.update_filter_status()
        
        # Re-trigger search to update table
        search_input = self.query_one(SearchInput)
        self.on_search(Input.Changed(search_input, search_input.value))

    async def load_data(self) -> None:
        """Load chains data from cache or network."""
        cached = get_cached_chains()
        if cached:
            self.chains = cached
            self.update_table(self.chains)
            return

        self.app.notify("Fetching chain data...", title="Syncing")
        try:
            self.chains = await fetch_chains()
            self.update_table(self.chains)
        except Exception as e:
            self.app.notify(f"Error loading data: {e}", severity="error")

    def update_table(self, chains: List[Dict[str, Any]]) -> None:
        table = self.query_one(ChainsTable)
        table.clear()
        self.filtered_chains = chains
        for i, chain in enumerate(chains):
            native = chain.get("nativeCurrency", {}).get("symbol", "N/A")
            table.add_row(
                chain.get("name", "Unknown"),
                str(chain.get("chainId", "N/A")),
                native,
                key=str(i)
            )

    @on(Input.Changed, "#search-input")
    def on_search(self, event: Input.Changed) -> None:
        query = event.value.lower()
        
        filtered = self.chains
        
        # Apply network type filter
        if self.filter_mode == "mainnet":
            filtered = [c for c in filtered if not c.get("isTestnet", False)]
        elif self.filter_mode == "testnet":
            filtered = [c for c in filtered if c.get("isTestnet", False)]
        
        # Apply search query
        if query:
            filtered = [
                c for c in filtered
                if query in c.get("name", "").lower() or query in str(c.get("chainId", ""))
            ]
        
        self.update_table(filtered)

    @on(Input.Submitted, "#search-input")
    def on_input_submitted(self) -> None:
        table = self.query_one(ChainsTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.filtered_chains):
            chain = self.filtered_chains[table.cursor_row]
            self.app.push_screen(RPCScreen(chain), self.on_rpc_selected)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(event.row_key.value)
        chain = self.filtered_chains[idx]
        self.app.push_screen(RPCScreen(chain), self.on_rpc_selected)

    def on_key(self, event: Any) -> None:
        if event.key == "tab":
            self.focus_next()
            event.stop()
            return
            
        if event.key == "enter" and self.focused and self.focused.id == "env-status":
            if self.current_env_rpc:
                self.app.exit(self.current_env_rpc)
            event.stop()
            return

        if event.key in ("up", "down", "pageup", "pagedown"):
            if self.focused and self.focused.id == "search-input":
                table = self.query_one(ChainsTable)
                if event.key == "up":
                    table.action_cursor_up()
                elif event.key == "down":
                    table.action_cursor_down()
                elif event.key == "pageup":
                    table.action_page_up()
                elif event.key == "pagedown":
                    table.action_page_down()
                event.stop()

    async def check_system_latency(self) -> None:
        import httpx
        import time
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
                response = await client.post(self.current_env_rpc, json=payload)
                if response.status_code == 200:
                    latency = (time.time() - start) * 1000
                    color = "#00ff00" if latency < 200 else "#ffff00" if latency < 500 else "#ff0000"
                    self.query_one("#env-latency", Label).update(f"[{color}]{latency:.0f} ms[/{color}]")
                else:
                    self.query_one("#env-latency", Label).update("[red]ERR[/red]")
        except Exception:
            self.query_one("#env-latency", Label).update("[red]ERR[/red]")

    def on_rpc_selected(self, rpc_url: str) -> None:
        if rpc_url:
            self.app.exit(rpc_url)
