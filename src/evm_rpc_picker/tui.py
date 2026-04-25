import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from platformdirs import user_cache_dir
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

CACHE_DIR = Path(user_cache_dir("evm-rpc-picker"))
CACHE_FILE = CACHE_DIR / "chains.json"
CHAINS_URL = "https://chainlist.org/rpcs.json"

class RPCListItem(ListItem):
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.latency: Optional[float] = None
        self.latency_label = Label("--- ms", classes="latency-label")

    def compose(self) -> ComposeResult:
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

class RPCScreen(ModalScreen[str]):
    """Screen to select RPC and check latency."""
    
    DEFAULT_CSS = """
    RPCScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #rpc-container {
        width: 80%;
        height: 70%;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }

    #rpc-list {
        height: 1fr;
        border: solid #313244;
        background: #181825;
        margin: 1 0;
        width: 100%;
    }

    #button-row {
        height: 3;
        width: 100%;
        margin-top: 1;
        content-align: center middle;
    }

    #button-row Button {
        margin: 0 1;
        min-width: 14;
    }

    ListItem.--highlight {
        background: #45475a;
        text-style: bold;
        color: #89b4fa;
    }

    #rpc-list:focus > ListItem.--highlight {
        background: #585b70;
        color: #f5c2e7;
    }

    RPCListItem {
        height: 1;
        width: 100%;
        padding: 0 1;
    }

    RPCListItem Horizontal {
        width: 100%;
        height: 1;
    }

    .latency-label {
        width: 12;
        text-align: right;
        text-style: bold;
    }

    .url-label {
        width: 1fr;
        color: #cdd6f4;
        content-align: left middle;
    }

    #rpc-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
        text-align: center;
    }

    .hint {
        color: #6c7086;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("b", "back", "Back"),
        ("r", "refresh", "Retry Latency Check"),
        ("s", "select_focused", "Select Focused RPC"),
    ]

    def __init__(self, chain: Dict[str, Any]):
        super().__init__()
        self.chain = chain
        # Extract URLs from list of objects (chainlist.org schema) or list of strings
        rpc_data = chain.get("rpc", [])
        self.rpcs = []
        for r in rpc_data:
            url = r.get("url") if isinstance(r, dict) else r
            if isinstance(url, str) and "${" not in url and url.startswith("http"):
                self.rpcs.append(url)

    def compose(self) -> ComposeResult:
        with Vertical(id="rpc-container"):
            yield Label(f"📡 RPC URLs for {self.chain['name']} (ID: {self.chain['chainId']})", id="rpc-title")
            yield ListView(id="rpc-list")
            with Horizontal(id="button-row"):
                yield Button("[u]B[/u]ack [ESC]", id="back-btn", variant="error")
                yield Button("[u]R[/u]etry", id="retry-btn", variant="primary")
                yield Button("[u]S[/u]elect [⏎]", id="select-btn", variant="success")

    async def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        for url in self.rpcs:
            list_view.append(RPCListItem(url))
        
        if not self.rpcs:
            list_view.append(ListItem(Label("[red]No public RPCs found (all require API keys)[/red]")))
        else:
            list_view.index = 0
            self.set_focus(list_view)
            self.check_latencies()

    @work(exclusive=True)
    async def check_latencies(self) -> None:
        """Ping RPCs in parallel."""
        tasks = []
        list_view = self.query_one(ListView)
        
        async with httpx.AsyncClient(timeout=2.5) as client:
            for item in list_view.query(RPCListItem):
                tasks.append(self.ping_rpc(client, item))
            await asyncio.gather(*tasks)
        
        # Gather results and sort URLs
        latencies = {item.url: item.latency for item in list_view.query(RPCListItem)}
        self.rpcs.sort(key=lambda url: latencies.get(url) if latencies.get(url) is not None else 1e9)
        
        # Re-populate list view with NEW items
        list_view.clear()
        for url in self.rpcs:
            new_item = RPCListItem(url)
            list_view.append(new_item)
            # Update latency display on the new item
            new_item.update_latency(latencies.get(url))
        
        # Wait a bit for the items to be processed in the DOM
        await asyncio.sleep(0.05)
        
        if self.rpcs:
            list_view.index = 0
            self.set_focus(list_view)

    async def ping_rpc(self, client: httpx.AsyncClient, item: RPCListItem) -> None:
        start_time = time.perf_counter()
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            response = await client.post(item.url, json=payload)
            response.raise_for_status()
            latency = (time.perf_counter() - start_time) * 1000
            item.update_latency(latency)
        except Exception:
            item.update_latency(None)

    def action_back(self) -> None:
        self.dismiss("")

    def action_refresh(self) -> None:
        self.check_latencies()

    def action_select_focused(self) -> None:
        list_view = self.query_one(ListView)
        if list_view.index is not None:
            item = list_view.children[list_view.index]
            if isinstance(item, RPCListItem):
                self.dismiss(item.url)

    @on(Button.Pressed, "#back-btn")
    def on_back_click(self) -> None:
        self.action_back()

    @on(Button.Pressed, "#retry-btn")
    def on_retry_click(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#select-btn")
    def on_select_click(self) -> None:
        self.action_select_focused()

    @on(ListView.Selected)
    def on_rpc_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RPCListItem):
            self.dismiss(event.item.url)

class SearchInput(Input):
    BINDINGS = [
        ("enter", "submit", "Select"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "app.load_data", "Refresh Data"),
    ]

class ChainsTable(DataTable):
    BINDINGS = [
        ("enter", "select_cursor", "Select"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "app.load_data", "Refresh Data"),
    ]

class ChainRPCPicker(App[str]):
    """TUI to search chains and select RPC URL."""
    
    TITLE = "EVM RPC Picker"
    
    CSS = """
    Screen {
        background: #11111b;
    }

    Header {
        background: #1e1e2e;
        color: #89b4fa;
        text-style: bold;
    }

    Footer {
        background: #1e1e2e;
        color: #cdd6f4;
    }

    #search-container {
        height: auto;
        padding: 1 2;
        background: #181825;
    }

    #search-input {
        border: solid #313244;
        background: #1e1e2e;
        color: #cdd6f4;
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
        ("escape", "quit", "Exit"),
        ("ctrl+r", "load_data", "Refresh Data"),
    ]

    def __init__(self):
        super().__init__()
        self.chains: List[Dict[str, Any]] = []
        self.filtered_chains: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="search-container"):
            yield SearchInput(placeholder="Search by name or chain ID (e.g. Ethereum, 1, Polygon...)", id="search-input")
        with Container(id="list-container"):
            yield ChainsTable(id="chain-table")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(ChainsTable)
        table.add_columns("Chain Name", "ID", "Currency")
        table.cursor_type = "row"
        self.query_one(SearchInput).focus()
        await self.load_data()

    def action_load_data(self) -> None:
        self.run_worker(self.load_data())

    async def load_data(self) -> None:
        """Load chains data from cache or network."""
        if CACHE_FILE.exists():
            mtime = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=24):
                try:
                    with open(CACHE_FILE, "r") as f:
                        self.chains = json.load(f)
                        self.update_table(self.chains)
                        return
                except Exception:
                    pass

        self.notify("Fetching chain data...", title="Syncing")
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            async with httpx.AsyncClient() as client:
                response = await client.get(CHAINS_URL)
                response.raise_for_status()
                data = response.json()
                # Only keep chains that have at least one RPC
                self.chains = [c for c in data if c.get("rpc")]
                with open(CACHE_FILE, "w") as f:
                    json.dump(self.chains, f)
                self.update_table(self.chains)
        except Exception as e:
            self.notify(f"Error loading data: {e}", severity="error")

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
        if not query:
            self.update_table(self.chains)
            return

        filtered = [
            c for c in self.chains
            if query in c.get("name", "").lower() or query in str(c.get("chainId", ""))
        ]
        self.update_table(filtered)

    @on(Input.Submitted, "#search-input")
    def on_input_submitted(self) -> None:
        table = self.query_one(ChainsTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.filtered_chains):
            chain = self.filtered_chains[table.cursor_row]
            self.push_screen(RPCScreen(chain), self.on_rpc_selected)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(event.row_key.value)
        chain = self.filtered_chains[idx]
        self.push_screen(RPCScreen(chain), self.on_rpc_selected)

    def on_key(self, event: events.Key) -> None:
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
            self.exit(rpc_url)

if __name__ == "__main__":
    app = ChainRPCPicker()
    result = app.run()
    if result:
        print(result)
