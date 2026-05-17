import asyncio
from typing import TYPE_CHECKING, Any

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from ..models import get_cached_chains
from ..utils.rpc_tester import check_rpc_latency

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


class FavoriteRPCTab(Static):
    """Tab displaying all favorited RPC URLs."""

    app: "ChainRPCPicker"

    BINDINGS = [
        Binding("ctrl+r", "refresh_latency", "Refresh", show=True),
        Binding("ctrl+l", "toggle_local_fav", "Fav (Local)", show=True),
        Binding("ctrl+g", "toggle_global_fav", "Fav (Global)", show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fav_urls: list[str] = []
        self.rpc_details: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        self.table = FavoriteRPCTable(id="favorite-rpcs-table", cursor_type="row")
        yield self.table

    def on_mount(self) -> None:
        self.table.add_columns("Fav", "Chain Name", "URL", "Latency")
        self.load_data()

    def load_data(self) -> None:
        fav_global = {u.strip() for u in self.app.config.global_config.get("favorite_rpcs", [])}
        fav_local = {u.strip() for u in self.app.config.local_config.get("favorite_rpcs", [])}
        all_favs = fav_global.union(fav_local)
        self.fav_urls = sorted(all_favs)

        chains = get_cached_chains() or []
        url_to_chain: dict[str, str] = {}
        for c in chains:
            c_name = c.get("name", "Unknown")
            for rpc_entry in c.get("rpc", []):
                url = rpc_entry if isinstance(rpc_entry, str) else rpc_entry.get("url", "")
                url = url.strip()
                if url:
                    url_to_chain[url] = c_name

        for rpcs in [
            self.app.config.global_config.get("custom_rpcs", {}),
            self.app.config.local_config.get("custom_rpcs", {}),
        ]:
            for cid_str, chain_rpcs in rpcs.items():
                fallback = next(
                    (c.get("name") for c in chains if str(c.get("chainId")) == cid_str),
                    f"Chain {cid_str}",
                )
                for r in chain_rpcs:
                    url = str(r.get("url", "")).strip()
                    url_to_chain[url] = str(r.get("name") or fallback)

        self.rpc_details = {}
        for url in self.fav_urls:
            self.rpc_details[url] = {
                "chain_name": url_to_chain.get(url.strip(), "Unknown Chain"),
                "url": url,
                "latency": "--- ms",
                "is_global": url in fav_global,
                "is_local": url in fav_local,
            }
        self.update_table()
        self.refresh_latency()

    def update_table(self) -> None:
        if not self.is_attached:
            return
        selected_url = self._get_selected_rpc_url()
        self.table.clear()

        def sort_key(url: str) -> tuple[str, float]:
            d = self.rpc_details[url]
            # Secondary sort by latency (numeric)
            import re

            lat_str = d["latency"]
            lat_val = 999999.0
            if "ms" in lat_str:
                match = re.search(r"(\d+)", lat_str)
                if match:
                    lat_val = float(match.group(1))

            return (d["chain_name"], lat_val)

        sorted_urls = sorted(self.fav_urls, key=sort_key)
        selected_index = 0
        for i, url in enumerate(sorted_urls):
            if url == selected_url:
                selected_index = i
            data = self.rpc_details[url]
            g_mark = "G" if data["is_global"] else " "
            l_mark = "L" if data["is_local"] else " "
            indicator = f"[[#89b4fa]{g_mark}{l_mark}[/]  ]"
            self.table.add_row(indicator, data["chain_name"], url, data["latency"], key=url)

        if self.table.row_count > 0:
            self.table.move_cursor(row=selected_index)

    def _get_selected_rpc_url(self) -> str | None:
        if self.table.row_count == 0 or not self.table.is_attached:
            return None
        try:
            row_key = self.table.coordinate_to_cell_key(self.table.cursor_coordinate).row_key
            return str(row_key.value)
        except Exception:
            return None

    def action_refresh_latency(self) -> None:
        """Action wrapper to refresh latency."""
        self.refresh_latency()

    @work(exclusive=True, thread=True)
    def refresh_latency(self) -> None:
        for url in self.fav_urls:
            self.rpc_details[url]["latency"] = "Testing..."
        self.app.call_from_thread(self.update_table)

        async def run_checks() -> None:
            results = await asyncio.gather(
                *(check_rpc_latency(u) for u in self.fav_urls), return_exceptions=True
            )
            for i, url in enumerate(self.fav_urls):
                res = results[i]
                self.rpc_details[url]["latency"] = (
                    "[red]Error[/red]" if isinstance(res, Exception) else res
                )
            self.app.call_from_thread(self.update_table)

        asyncio.run(run_checks())

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        url = self._get_selected_rpc_url()
        if url and hasattr(self.app.screen, "_on_rpc_selected"):
            self.app.screen._on_rpc_selected(url)

    def action_toggle_global_fav(self) -> None:
        url = self._get_selected_rpc_url()
        if not url:
            return
        self.app.config.toggle_favorite_rpc(url, is_global=True)
        self.rpc_details[url]["is_global"] = url in set(
            self.app.config.global_config.get("favorite_rpcs", [])
        )
        self._sync_favs_and_update()

    def action_toggle_local_fav(self) -> None:
        url = self._get_selected_rpc_url()
        if not url:
            return
        self.app.config.toggle_favorite_rpc(url, is_global=False)
        self.rpc_details[url]["is_local"] = url in set(
            self.app.config.local_config.get("favorite_rpcs", [])
        )
        self._sync_favs_and_update()

    def _sync_favs_and_update(self) -> None:
        to_remove = [
            u for u, d in self.rpc_details.items() if not d["is_global"] and not d["is_local"]
        ]
        for u in to_remove:
            self.fav_urls.remove(u)
            del self.rpc_details[u]
        self.update_table()
