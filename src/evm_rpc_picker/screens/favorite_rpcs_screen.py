import asyncio
from typing import TYPE_CHECKING, Any

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..models import get_cached_chains
from ..utils.rpc_tester import check_rpc_latency
from ..widgets.custom_header import CustomHeader

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker


class FavoriteRPCTable(DataTable[Any]):
    BINDINGS = [
        Binding("home", "cursor_top", "Top", show=False),
        Binding("end", "cursor_bottom", "Bottom", show=False),
    ]

    def action_cursor_top(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)


class FavoriteRPCScreen(Screen[str]):
    """Screen displaying all favorited RPC URLs."""

    app: "ChainRPCPicker"

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("enter", "submit", "Select RPC", tooltip="Select the highlighted RPC"),
        Binding("ctrl+r", "refresh_latency", "Retest Latency"),
        Binding("ctrl+l", "toggle_local_fav", "Toggle Local Fav"),
        Binding("ctrl+g", "toggle_global_fav", "Toggle Global Fav"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.fav_urls: list[str] = []
        self.rpc_details: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        yield CustomHeader("Ξ EVM RPC Picker / ★ Favorite RPCs")
        self.table = FavoriteRPCTable(id="favorite-rpcs-table", cursor_type="row")
        yield self.table
        yield Footer()

    def on_mount(self) -> None:
        self.table.add_columns("Fav", "Chain Name", "URL", "Latency")
        self._load_data()

    def _load_data(self) -> None:
        """Gather all favorited RPCs and resolve their chain names."""
        fav_global = set(self.app.config.global_config.get("favorite_rpcs", []))
        fav_local = set(self.app.config.local_config.get("favorite_rpcs", []))
        all_favs = fav_global.union(fav_local)

        self.fav_urls = sorted(list(all_favs))

        # We need chain info. Let's try to map URL -> Chain Name
        chains = get_cached_chains() or []
        url_to_chain: dict[str, str] = {}
        
        # Build map from chainlist
        for c in chains:
            c_name = c.get("name", "Unknown")
            for rpc_entry in c.get("rpc", []):
                url = None
                if isinstance(rpc_entry, str):
                    url = rpc_entry
                elif isinstance(rpc_entry, dict):
                    url = rpc_entry.get("url")
                
                if url:
                    url_to_chain[url] = c_name

        # Also check custom RPCs
        custom_rpcs_global = self.app.config.global_config.get("custom_rpcs", {})
        custom_rpcs_local = self.app.config.local_config.get("custom_rpcs", {})
        
        for cid_str, rpcs in custom_rpcs_global.items():
            fallback_name = next((c.get("name", "Unknown") for c in chains if str(c.get("chainId")) == cid_str), f"Chain {cid_str}")
            for r in rpcs:
                # Custom name override
                url_to_chain[r.get("url")] = r.get("name") or fallback_name
                
        for cid_str, rpcs in custom_rpcs_local.items():
            fallback_name = next((c.get("name", "Unknown") for c in chains if str(c.get("chainId")) == cid_str), f"Chain {cid_str}")
            for r in rpcs:
                # Custom name override
                url_to_chain[r.get("url")] = r.get("name") or fallback_name

        self.rpc_details = {}
        for url in self.fav_urls:
            chain_name = url_to_chain.get(url, "Unknown Chain")
            
            # Setup details
            self.rpc_details[url] = {
                "chain_name": chain_name,
                "url": url,
                "latency": "--- ms",
                "is_global": url in fav_global,
                "is_local": url in fav_local,
            }

        self.update_table()
        self.action_refresh_latency()

    def update_table(self) -> None:
        """Update the UI table without re-testing latency."""
        selected_url = self._get_selected_rpc_url()
        self.table.clear()

        # Sort: Local > Global > URL
        def sort_key(url: str) -> tuple[int, str]:
            data = self.rpc_details[url]
            score = 0
            if data["is_local"]:
                score -= 2
            elif data["is_global"]:
                score -= 1
            return (score, url)

        sorted_urls = sorted(self.fav_urls, key=sort_key)
        
        selected_index = 0
        for i, url in enumerate(sorted_urls):
            if url == selected_url:
                selected_index = i
                
            data = self.rpc_details[url]
            g_str = "[#89b4fa]G[/]" if data["is_global"] else " "
            l_str = "[#89b4fa]L[/]" if data["is_local"] else " "
            indicator = f"[{g_str}{l_str}  ]"

            self.table.add_row(
                indicator,
                data["chain_name"],
                url,
                data["latency"],
                key=url,
            )

        if self.table.row_count > 0:
            self.table.move_cursor(row=selected_index)

    def _get_selected_rpc_url(self) -> str | None:
        if self.table.row_count == 0 or not self.table.is_attached:
            return None
        try:
            row_key = self.table.coordinate_to_cell_key(self.table.cursor_coordinate).row_key
            return str(row_key.value)
        except (ValueError, TypeError, AttributeError, IndexError):
            return None

    @work(exclusive=True, thread=True)
    def action_refresh_latency(self) -> None:
        """Retest latency for all favorited RPCs."""
        for url in self.fav_urls:
            self.rpc_details[url]["latency"] = "Testing..."
        self.app.call_from_thread(self.update_table)

        async def run_checks() -> None:
            tasks = []
            for url in self.fav_urls:
                tasks.append(check_rpc_latency(url))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, url in enumerate(self.fav_urls):
                res = results[i]
                if isinstance(res, Exception):
                    self.rpc_details[url]["latency"] = "[red]Error[/red]"
                else:
                    self.rpc_details[url]["latency"] = res

            self.app.call_from_thread(self.update_table)

        asyncio.run(run_checks())

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        url = self._get_selected_rpc_url()
        if url:
            self.dismiss(url)

    def action_toggle_global_fav(self) -> None:
        url = self._get_selected_rpc_url()
        if not url:
            return
        self.app.config.toggle_favorite_rpc(url, is_global=True)
        # Update our internal state to avoid a full reload
        fav_global = set(self.app.config.global_config.get("favorite_rpcs", []))
        self.rpc_details[url]["is_global"] = url in fav_global
        self._sync_favs_and_update()

    def action_toggle_local_fav(self) -> None:
        url = self._get_selected_rpc_url()
        if not url:
            return
        self.app.config.toggle_favorite_rpc(url, is_global=False)
        fav_local = set(self.app.config.local_config.get("favorite_rpcs", []))
        self.rpc_details[url]["is_local"] = url in fav_local
        self._sync_favs_and_update()

    def _sync_favs_and_update(self) -> None:
        """Remove RPCs that are no longer favorited at all, then update UI."""
        to_remove = []
        for url, data in self.rpc_details.items():
            if not data["is_global"] and not data["is_local"]:
                to_remove.append(url)
                
        for url in to_remove:
            self.fav_urls.remove(url)
            del self.rpc_details[url]
            
        self.update_table()
