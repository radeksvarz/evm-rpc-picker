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

    DataTable > .datatable--cursor {
        background: #89b4fa 30%;
    }

    DataTable > .datatable--header {
        background: #313244;
        color: #f5e0dc;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("enter", "submit", "Select"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "load_data", "Refresh Data"),
        ("ctrl+t", "toggle_filter", "Toggle Filter"),
    ]

    def __init__(self):
        super().__init__()
        self.chains: List[Dict[str, Any]] = []
        self.filtered_chains: List[Dict[str, Any]] = []
        self.filter_mode: str = "all"  # all, mainnet, testnet

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="search-container"):
            yield SearchInput(placeholder="Search by name or chain ID (e.g. Ethereum, 1, Polygon...)", id="search-input")
            yield Label("Filter: ALL", id="filter-status")
        with Container(id="list-container"):
            yield ChainsTable(id="chain-table")
        yield Footer()

    async def on_mount(self) -> None:
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

    def on_rpc_selected(self, rpc_url: str) -> None:
        if rpc_url:
            self.app.exit(rpc_url)
