from typing import TYPE_CHECKING, Any

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Label, Static

from ..context import ContextDetector
from ..models import fetch_chains, get_cached_chains
from ..screens.rpc_screen import RPCScreen
from ..widgets import ChainsTable, ContextBar, SearchInput

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker


class ChainlistTab(Static):
    """View displaying the searchable list of chains from chainlist.org."""

    app: "ChainRPCPicker"

    BINDINGS = [
        Binding("ctrl+f", "toggle_filter_favs", "Favorite chains", show=True),
        Binding("ctrl+t", "toggle_filter_type", "Chain Type", show=True),
        Binding("ctrl+l", "toggle_favorite", "Fav (Local)", show=True),
        Binding("ctrl+g", "toggle_global_favorite", "Fav (Global)", show=True),
    ]

    DEFAULT_CSS = """
    ChainlistTab {
        width: 100%;
        height: 1fr;
    }

    #search-container {
        height: auto;
        padding: 1 2;
        background: #181825;
        align: left middle;
    }

    #search-input {
        width: 1fr;
        height: 3;
        border: solid #313244;
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 0 1;
        content-align: left middle;
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

    #list-container {
        padding: 0 2;
        height: 1fr;
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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.chains: list[dict[str, Any]] = []
        self.filtered_chains: list[dict[str, Any]] = []
        self.filter_type: str = "all"  # all, testnet, mainnet
        self.filter_favorites_only: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="search-container"):
            search_input = SearchInput(id="search-input")
            search_input.placeholder = "Search by name or chain ID (e.g. Ethereum, 1, Polygon...)"
            yield search_input
            yield Label("Filter: ALL", id="filter-status")

        with Container(id="list-container"):
            table = ChainsTable(id="chain-table")
            table.can_focus = True
            yield table
            yield ContextBar(id="context-bar-widget")

    async def on_mount(self) -> None:
        table = self.query_one(ChainsTable)
        table.add_columns("", "Chain Name", "ID", "Short", "Currency")
        table.cursor_type = "row"
        table.focus()
        await self.load_data()

    def update_filter_status(self) -> None:
        status_label = self.query_one("#filter-status", Label)
        star = "* " if self.filter_favorites_only else ""
        type_str = self.filter_type.upper()
        status_label.update(f"Filter: {star}{type_str}")

    def action_toggle_filter_favs(self) -> None:
        self.filter_favorites_only = not self.filter_favorites_only
        self.apply_filter()

    def action_toggle_filter_type(self) -> None:
        modes = ["all", "testnet", "mainnet"]
        current_idx = modes.index(self.filter_type)
        self.filter_type = modes[(current_idx + 1) % len(modes)]
        self.apply_filter()

    def action_toggle_favorite(self) -> None:
        table = self.query_one(ChainsTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            idx = int(str(row_key.value))
        except (ValueError, TypeError, AttributeError):
            return

        if 0 <= idx < len(self.filtered_chains):
            chain = self.filtered_chains[idx]
            chain_id = chain.get("chainId")
            if chain_id is not None:
                self.app.config.toggle_favorite(int(chain_id), is_global=False)
                self.refresh_table(toggled_chain_id=int(chain_id))

    def action_toggle_global_favorite(self) -> None:
        table = self.query_one(ChainsTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            idx = int(str(row_key.value))
        except (ValueError, TypeError, AttributeError):
            return

        if 0 <= idx < len(self.filtered_chains):
            chain = self.filtered_chains[idx]
            chain_id = chain.get("chainId")
            if chain_id is not None:
                self.app.config.toggle_favorite(int(chain_id), is_global=True)
                self.refresh_table(toggled_chain_id=int(chain_id))

    def refresh_table(self, toggled_chain_id: int | None = None) -> None:
        """Trigger search update to refresh table contents and indicators."""
        self.query_one(ContextBar).update_status()
        self.apply_filter(toggled_chain_id=toggled_chain_id)

    async def refresh_data(self) -> None:
        """Force refresh data from chainlist.org."""
        await self.load_data(force=True)

    async def load_data(self, force: bool = False) -> None:
        """Load chains data from cache or network."""
        table = self.query_one(ChainsTable)

        if not force:
            cached = get_cached_chains()
            if cached:
                self.chains = cached
                self.apply_filter()
                return

        self.app.notify("Fetching chain data...", title="Syncing")
        table.loading = True
        try:
            self.chains = await fetch_chains()
            self.apply_filter()
        except Exception as e:
            self.app.notify(f"Error loading data: {e}", severity="error")
        finally:
            table.loading = False

    def update_table(self, chains: list[dict[str, Any]]) -> None:
        table = self.query_one(ChainsTable)
        table.clear()

        fav_global = set(self.app.config.global_config.get("favorite_chains", []))
        fav_local = set(self.app.config.local_config.get("favorite_chains", []))

        foundry_endpoints = ContextDetector.get_foundry_rpc_endpoints()
        hardhat_names = ContextDetector.get_hardhat_networks()

        foundry_ids = ContextDetector.match_names_to_ids(foundry_endpoints, self.chains)
        hardhat_data = dict.fromkeys(hardhat_names, "")
        hardhat_ids = ContextDetector.match_names_to_ids(hardhat_data, self.chains)

        def sort_key(c: dict[str, Any]) -> int:
            cid = c.get("chainId")
            if cid in fav_local:
                return 0
            if cid in fav_global:
                return 1
            if cid in foundry_ids or cid in hardhat_ids:
                return 2
            return 3

        sorted_chains = sorted(chains, key=sort_key)
        self.filtered_chains = sorted_chains

        for i, chain in enumerate(sorted_chains):
            cid = chain.get("chainId")

            is_g = cid in fav_global
            is_local_f = cid in fav_local
            is_f = cid in foundry_ids
            is_h = cid in hardhat_ids

            if any([is_g, is_local_f, is_f, is_h]):
                g_str = "[#89b4fa]G[/]" if is_g else " "
                l_str = "[#89b4fa]L[/]" if is_local_f else " "
                f_str = "[#89b4fa]F[/]" if is_f else " "
                h_str = "[#89b4fa]H[/]" if is_h else " "
                indicator = f"[{g_str}{l_str}{f_str}{h_str}]"
            else:
                indicator = ""

            native = chain.get("nativeCurrency", {}).get("symbol", "N/A")
            table.add_row(
                indicator,
                chain.get("name", "Unknown"),
                str(cid),
                chain.get("shortName", "N/A"),
                native,
                key=str(i),
            )

    def apply_filter(self, toggled_chain_id: int | None = None) -> None:
        query = self.query_one("#search-input", SearchInput).value.lower()
        filtered = self.chains

        if self.filter_type == "mainnet":
            filtered = [c for c in filtered if not c.get("isTestnet", False)]
        elif self.filter_type == "testnet":
            filtered = [c for c in filtered if c.get("isTestnet", False)]

        if self.filter_favorites_only:
            fav_all = set(self.app.config.get_favorites())
            foundry_data = ContextDetector.get_foundry_rpc_endpoints()
            hardhat_data = dict.fromkeys(ContextDetector.get_hardhat_networks(), "")
            all_context_data = {**foundry_data, **hardhat_data}
            context_ids = ContextDetector.match_names_to_ids(all_context_data, self.chains)
            filtered = [
                c
                for c in filtered
                if c.get("chainId") in fav_all or c.get("chainId") in context_ids
            ]

        if query:
            filtered = [
                c
                for c in filtered
                if query in c.get("name", "").lower()
                or query in str(c.get("chainId", ""))
                or query in c.get("shortName", "").lower()
            ]

        self.filtered_chains = filtered
        self.update_filter_status()
        self.update_table(filtered)

        table = self.query_one(ChainsTable)
        new_row = 0
        if toggled_chain_id is not None:
            for i, c in enumerate(self.filtered_chains):
                if c.get("chainId") == toggled_chain_id:
                    new_row = i
                    break
        else:
            if table.cursor_row is not None and table.cursor_row < len(filtered):
                new_row = table.cursor_row

        if filtered:
            table.move_cursor(row=new_row)

    @on(DataTable.RowSelected, "#chain-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.filtered_chains):
                chain = self.filtered_chains[idx]
                self.app.push_screen(RPCScreen(chain), self.app.screen._on_rpc_selected)  # type: ignore[attr-defined]

    def on_key(self, event: events.Key) -> None:
        search_input = self.query_one(SearchInput)

        if event.key == "backspace":
            if search_input.value:
                search_input.value = search_input.value[:-1]
                self.apply_filter()
                event.stop()
        elif event.is_printable and event.character:
            search_input.value += event.character
            self.apply_filter()
            event.stop()
        elif event.key == "escape":
            if search_input.value:
                search_input.value = ""
                self.apply_filter()
                event.stop()
