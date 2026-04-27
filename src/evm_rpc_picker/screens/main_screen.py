from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker

from textual import events, on
from ..commands import RefreshDataProvider
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label

from ..context import ContextDetector
from ..models import fetch_chains, get_cached_chains
from ..widgets import ChainsTable, CustomHeader, EnvStatus, SearchInput
from .confirm_modal import ConfirmModal
from .rpc_screen import RPCScreen







class MainScreen(Screen[str]):
    """Main screen for searching and listing chains."""

    app: "ChainRPCPicker"

    COMMANDS = Screen.COMMANDS | {RefreshDataProvider}

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
    """

    BINDINGS = [
        ("enter", "submit", "Select"),
        ("escape", "app.quit", "Cancel"),
        ("/", "focus_search", "Search"),
        ("ctrl+f", "toggle_filter_favs", "Filter Favs"),
        ("ctrl+t", "toggle_filter_type", "Filter Type"),
        ("ctrl+space", "toggle_favorite", "Fav (P)"),
        ("ctrl+shift+space", "toggle_global_favorite", "Fav (G)"),
        Binding("ctrl+r", "refresh_data", "Refresh Data from chainlist.org", show=False),
        ("c", "init_project", "Init"),
        Binding("tab", "focus_next", "Switch", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.chains: list[dict[str, Any]] = []
        self.filtered_chains: list[dict[str, Any]] = []
        self.filter_type: str = "all"  # all, mainnet, testnet
        self.filter_favorites_only: bool = False

    def compose(self) -> ComposeResult:
        yield CustomHeader()
        with Horizontal(id="search-container"):
            yield SearchInput(
                placeholder="Search by name or chain ID (e.g. Ethereum, 1, Polygon...)",
                id="search-input",
            )
            yield Label("Filter: ALL", id="filter-status")
        with Container(id="list-container"):
            table = ChainsTable(id="chain-table")
            table.can_focus = True
            yield table
        yield EnvStatus(id="env-status-widget")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(ChainsTable)
        table.add_columns("", "Chain Name", "ID", "Short", "Currency")
        table.cursor_type = "row"
        table.focus()
        await self.action_load_data()

    def update_filter_status(self) -> None:
        status_label = self.query_one("#filter-status", Label)
        star = "* " if self.filter_favorites_only else ""
        type_str = self.filter_type.upper()
        status_label.update(f"Filter: {star}{type_str}")

    def action_focus_search(self) -> None:
        self.query_one("#search-input").focus()

    def action_toggle_filter_favs(self) -> None:
        self.filter_favorites_only = not self.filter_favorites_only
        self.apply_filter()

    def action_toggle_filter_type(self) -> None:
        modes = ["all", "mainnet", "testnet"]
        current_idx = modes.index(self.filter_type)
        self.filter_type = modes[(current_idx + 1) % len(modes)]
        self.apply_filter()

    def action_toggle_favorite(self) -> None:
        table = self.query_one(ChainsTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.filtered_chains):
            chain = self.filtered_chains[table.cursor_row]
            chain_id = chain.get("chainId")
            if chain_id is None:
                return

            if not self.app.config.local_config_exists():
                self.app.push_screen(
                    ConfirmModal("Local config not found. Create .rpc-picker.toml?"),
                    self._on_init_confirm,
                )
                return

            self.app.config.toggle_favorite(int(chain_id), is_global=False)
            self.refresh_table()

    def action_toggle_global_favorite(self) -> None:
        table = self.query_one(ChainsTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.filtered_chains):
            chain = self.filtered_chains[table.cursor_row]
            chain_id = chain.get("chainId")
            if chain_id is not None:
                self.app.config.toggle_favorite(int(chain_id), is_global=True)
                self.refresh_table()

    def action_init_project(self) -> None:
        if self.app.config.local_config_exists():
            self.app.notify("Local config already exists.", severity="information")
        else:
            self.app.config.init_local_config()
            self.app.notify("Created .rpc-picker.toml", title="Project Initialized")
            self.refresh_table()

    def refresh_table(self) -> None:
        """Trigger search update to refresh table contents and indicators."""
        self.apply_filter()

    async def action_refresh_data(self) -> None:
        """Force refresh data from chainlist.org."""
        await self.action_load_data(force=True)

    async def action_load_data(self, force: bool = False) -> None:
        """Load chains data from cache or network."""
        if not force:
            cached = get_cached_chains()
            if cached:
                self.chains = cached
                self.apply_filter()
                return

        self.app.notify("Fetching chain data...", title="Syncing")
        try:
            self.chains = await fetch_chains()
            self.apply_filter()
        except Exception as e:
            self.app.notify(f"Error loading data: {e}", severity="error")

    def update_table(self, chains: list[dict[str, Any]]) -> None:
        table = self.query_one(ChainsTable)
        table.clear()

        fav_global = self.app.config.get_favorites(project_only=False)
        fav_local = self.app.config.get_favorites(project_only=True)

        # Get chains mentioned in local tool configs (Foundry, etc.)
        context_names = ContextDetector.get_context_chain_names()
        context_ids = {
            c["chainId"]
            for c in chains
            if c["name"].lower() in [n.lower() for n in context_names]
            or c.get("shortName", "").lower() in [n.lower() for n in context_names]
        }

        # Sort: Local > Global Favorite > Others
        def sort_key(c: dict[str, Any]) -> int:
            cid = c.get("chainId")
            if cid in fav_local or cid in context_ids:
                return 0
            if cid in fav_global:
                return 1
            return 2

        sorted_chains = sorted(chains, key=sort_key)
        self.filtered_chains = sorted_chains

        for i, chain in enumerate(sorted_chains):
            cid = chain.get("chainId")
            indicator = ""

            is_local = cid in fav_local or cid in context_ids
            is_global = cid in fav_global

            if is_local:
                indicator = "* [P]"
            elif is_global:
                indicator = "*"

            native = chain.get("nativeCurrency", {}).get("symbol", "N/A")
            table.add_row(
                indicator,
                chain.get("name", "Unknown"),
                str(cid),
                chain.get("shortName", "N/A"),
                native,
                key=str(i),
            )

    @on(Input.Changed, "#search-input")
    def on_search(self, event: Input.Changed) -> None:
        self.apply_filter()

    def apply_filter(self) -> None:
        query = self.query_one("#search-input", SearchInput).value.lower()
        filtered = self.chains

        # 1. Apply network type filter
        if self.filter_type == "mainnet":
            filtered = [c for c in filtered if not c.get("isTestnet", False)]
        elif self.filter_type == "testnet":
            filtered = [c for c in filtered if c.get("isTestnet", False)]

        # 2. Apply favorites filter
        if self.filter_favorites_only:
            fav_all = self.app.config.get_favorites()
            # Context chains are also treated as favorites in this view
            context_names = ContextDetector.get_context_chain_names()
            context_ids = {
                c["chainId"]
                for c in self.chains
                if c["name"].lower() in [n.lower() for n in context_names]
                or c.get("shortName", "").lower() in [n.lower() for n in context_names]
            }
            filtered = [
                c
                for c in filtered
                if c.get("chainId") in fav_all or c.get("chainId") in context_ids
            ]

        # 3. Apply search query
        if query:
            filtered = [
                c for c in filtered if query in c["name"].lower() or query in str(c["chainId"])
            ]

        self.filtered_chains = filtered
        self.update_filter_status()
        self.update_table(filtered)

        # Ensure cursor is visible if we have results
        table = self.query_one(ChainsTable)
        if filtered and (table.cursor_row is None or table.cursor_row >= len(filtered)):
            table.move_cursor(row=0)

    @on(DataTable.RowSelected, "#chain-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter) to open RPC screen."""
        if event.row_key.value is not None:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.filtered_chains):
                chain = self.filtered_chains[idx]
                self.app.push_screen(RPCScreen(chain), self._on_rpc_selected)

    def _on_rpc_selected(self, rpc_url: str | None) -> None:
        if rpc_url:
            self.app.exit(rpc_url)

    def on_key(self, event: events.Key) -> None:
        """Handle alpha-numeric keys to focus and type into search."""
        if event.is_printable and len(event.key) == 1:
            search_input = self.query_one(SearchInput)
            if not search_input.has_focus:
                search_input.focus()
                search_input.value += event.key
                # Textual handles the cursor position usually,
                # but we might need to prevent double character if we are not careful.
                # Actually, if we focus it here, the event might bubble up or be handled by search.
                event.stop()

    def _on_init_confirm(self, confirmed: bool | None) -> None:
        if confirmed:
            self.app.config.init_local_config()
            self.app.notify("Created .rpc-picker.toml")
            self.refresh_table()
