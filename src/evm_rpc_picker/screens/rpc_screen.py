import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker

import httpx
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label

from ..context import ContextDetector
from ..widgets.custom_header import CustomHeader
from .password_modal import PasswordModal


class RPCTable(DataTable):
    BINDINGS = [
        Binding("home", "cursor_top", "Top", show=False),
        Binding("end", "cursor_bottom", "Bottom", show=False),
        Binding("enter", "submit", "Select RPC"),
    ]

    def action_cursor_top(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)


class RPCScreen(Screen[str]):
    """Screen to select RPC and check latency."""

    @property
    def picker_app(self) -> "ChainRPCPicker":
        """Typed access to the main app instance."""
        from typing import cast

        return cast("ChainRPCPicker", self.app)

    DEFAULT_CSS = """
    RPCScreen {
        layout: vertical;
    }

    #rpc-header {
        height: auto;
        padding: 1 2;
        background: #181825;
        border-bottom: solid #313244;
    }

    #header-left {
        width: 1fr;
    }

    #header-right {
        width: auto;
        text-align: right;
        color: #6c7086;
        text-style: italic;
    }

    #rpc-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("enter", "submit", "Select RPC", tooltip="Select the highlighted RPC"),
        Binding("escape", "dismiss(None)", "Back"),
        Binding("ctrl+r", "retry", "Retest"),
        Binding(
            "ctrl+l",
            "screen.toggle_favorite",
            "Fav (Local)",
            tooltip="Add/remove from local project favorites",
        ),
        Binding(
            "ctrl+g",
            "screen.toggle_global_favorite",
            "Fav (Global)",
            tooltip="Add/remove from global favorites",
        ),
    ]

    def __init__(self, chain: dict[str, Any]):
        super().__init__()
        self.chain = chain
        self.rpc_data: list[dict[str, Any]] = self._gather_rpcs()
        self.current_sorted_rpcs: list[dict[str, Any]] = []

    def _gather_rpcs(self) -> list[dict[str, Any]]:
        rpcs = []
        rpcs.extend(self._gather_public_rpcs())
        rpcs.extend(self._gather_custom_rpcs())
        rpcs.extend(self._gather_context_rpcs())

        # Deduplicate by URL to avoid showing the same endpoint twice
        seen_urls = set()
        unique_rpcs = []
        for r in rpcs:
            url = r.get("url")
            if url and url not in seen_urls:
                unique_rpcs.append(r)
                seen_urls.add(url)
        return unique_rpcs

    def _gather_public_rpcs(self) -> list[dict[str, Any]]:
        rpcs: list[dict[str, Any]] = []
        raw_rpc = self.chain.get("rpc", [])
        for r in raw_rpc:
            url = None
            tracking = "unspecified"
            if isinstance(r, str):
                url = r.strip()
            elif isinstance(r, dict):
                url = r.get("url", "").strip()
                tracking = r.get("tracking", "unspecified")

            if url and not url.startswith("wss://"):
                rpcs.append(
                    {
                        "url": url,
                        "display_url": url,
                        "tracking": tracking,
                        "source": "public",
                        "is_secret": False,
                        "needs_password": False,
                    }
                )
        return rpcs

    def _gather_custom_rpcs(self) -> list[dict[str, Any]]:
        rpcs: list[dict[str, Any]] = []
        cm = self.picker_app.config
        cid = self.chain.get("chainId")
        if cid is None:
            return rpcs

        custom = cm.get_custom_rpcs(int(cid))
        for c in custom:
            c = cm.normalize_custom_rpc(c)
            url = c.get("url", "").strip()
            is_encrypted = c.get("rpc_password_protected", False)
            has_secrets = c.get("has_secrets", False)
            rpc_id = str(c.get("id"))
            if not rpc_id:
                continue

            display_url = url
            final_url = url
            needs_password = is_encrypted

            if has_secrets:
                if not is_encrypted:
                    # Try to fetch immediately
                    secret_data = cm.load_rpc_secret(rpc_id)
                    if secret_data.get("status") == "ok":
                        key = secret_data.get("api_key", "")
                        final_url = cm.resolve_url_secrets(url, rpc_id, key)
                        display_url = final_url
                    else:
                        display_url = cm.mask_url_secrets(url, rpc_id)
                else:
                    display_url = cm.mask_url_secrets(url, rpc_id)
            else:
                display_url = cm.mask_url_secrets(url, rpc_id)

            rpcs.append(
                {
                    "id": rpc_id,
                    "name": c.get("name", ""),
                    "url": final_url,
                    "display_url": display_url,
                    "tracking": "none",
                    "source": c.get("source", "global"),
                    "is_secret": has_secrets,
                    "needs_password": needs_password,
                    "note": c.get("note", ""),
                    "rpc_password_protected": is_encrypted,
                }
            )
        return rpcs

    def _gather_context_rpcs(self) -> list[dict[str, Any]]:
        rpcs: list[dict[str, Any]] = []
        foundry = ContextDetector.get_foundry_rpc_endpoints()
        name = self.chain.get("name", "").lower()
        short = self.chain.get("shortName", "").lower()
        for f_name, f_url in foundry.items():
            if f_name.lower() in (name, short):
                rpcs.append(
                    {
                        "url": f_url.strip(),
                        "display_url": f_url.strip(),
                        "tracking": "none",
                        "source": "foundry",
                        "is_secret": False,
                        "needs_password": False,
                    }
                )
        return rpcs

    def compose(self) -> ComposeResult:
        name = self.chain.get("name", "Unknown")
        cid = str(self.chain.get("chainId", "N/A"))
        short = self.chain.get("shortName", "N/A")
        native = self.chain.get("nativeCurrency", {}).get("symbol", "N/A")
        info_url = self.chain.get("infoURL", "")

        yield CustomHeader(f"Ξ EVM RPC Picker / Chainlist.org / {name}")
        with Horizontal(id="rpc-header"):
            yield Label(
                f"ID: {cid} | Short: {short} | Currency: {native}",
                id="header-left",
            )
            yield Label(f"{info_url}", id="header-right")

        table = RPCTable(id="rpc-table", cursor_type="row")
        yield table
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "URL", "Privacy", "Latency")
        await self.refresh_rpcs()

    async def refresh_rpcs(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        table.loading = True
        self.picker_app.notify("Latency testing RPC endpoints...", title="Testing RPCs")

        items_to_ping = []
        for r in self.rpc_data:
            item = dict(r)
            item["latency"] = None
            item["actual_url"] = item.get("url", "")
            items_to_ping.append(item)

        # Run latency checks in background
        self.run_worker(self.check_latencies(items_to_ping))

    async def check_latencies(self, items: list[dict[str, Any]]) -> None:
        async with httpx.AsyncClient(timeout=2.5) as client:
            tasks = [self.ping_rpc(client, item) for item in items]
            await asyncio.gather(*tasks)

        self.rpc_data_with_latency = items
        self.update_table()

    def _on_url_ready(self, url: str) -> None:
        # We need to call the callback that MainScreen expects
        if hasattr(self.picker_app.screen, "_on_rpc_selected"):
            self.picker_app.screen._on_rpc_selected(url)

    def update_table(self) -> None:
        """Sort and render the RPC table based on current data."""
        if not self.is_attached:
            return
        if not hasattr(self, "rpc_data_with_latency"):
            return

        table = self.query_one(DataTable)

        # Preserve selection
        selected_url = None
        selected_rpc = self._get_selected_rpc()
        if selected_rpc:
            selected_url = selected_rpc.get("url")

        items = self.rpc_data_with_latency

        # Get favorites for sorting
        fav_global = self.picker_app.config.get_favorite_rpcs(project_only=False)
        fav_local = self.picker_app.config.get_favorite_rpcs(project_only=True)

        # Sort by favorite status then latency (None at the end)
        def sort_key(x: dict[str, Any]) -> tuple[int, bool, float]:
            url = x.get("url", "")
            is_fav_local = url in fav_local
            is_fav_global = url in fav_global

            # Priority: Local Fav > Global Fav > Others
            priority = 0 if is_fav_local else (1 if is_fav_global else 2)
            has_no_latency = x["latency"] is None
            latency = x["latency"] or 9999
            return (priority, has_no_latency, latency)

        self.current_sorted_rpcs = sorted(items, key=sort_key)

        table.clear()

        fav_global_urls = self.picker_app.config.global_config.get("favorite_rpcs", [])
        fav_local_urls = self.picker_app.config.local_config.get("favorite_rpcs", [])

        new_index = 0
        for i, d in enumerate(self.current_sorted_rpcs):
            url = d.get("url", "")
            if selected_url and url == selected_url:
                new_index = i

            url_display = self._format_url_display(d)
            indicator = self._get_rpc_indicator(d, fav_global_urls, fav_local_urls)
            tracking_str = self._get_tracking_label(d)
            lat_str = self._get_latency_label(d.get("latency"))

            table.add_row(indicator, url_display, tracking_str, lat_str, key=str(i))

        table.loading = False
        if table.row_count > 0:
            table.move_cursor(row=new_index)
            table.focus()

    def _format_url_display(self, d: dict[str, Any]) -> str:
        url_display = str(d.get("display_url", ""))
        if d.get("name"):
            url_display = f"[{d['name']}] {url_display}"
        if d.get("rpc_password_protected"):
            url_display = f"[🔒] {url_display}"
        return url_display

    def _get_rpc_indicator(
        self, d: dict[str, Any], fav_g_urls: list[str], fav_l_urls: list[str]
    ) -> str:
        url = d.get("url", "")
        is_fav_g = url in fav_g_urls
        is_fav_l = url in fav_l_urls
        source = d.get("source", "")
        is_f = source == "foundry"
        is_h = source == "hardhat"

        if source == "global":
            is_fav_g = True
        if source == "project":
            is_fav_l = True

        if any([is_fav_g, is_fav_l, is_f, is_h]):
            g_str = "[#89b4fa]G[/]" if is_fav_g else " "
            l_str = "[#89b4fa]L[/]" if is_fav_l else " "
            f_str = "[#89b4fa]F[/]" if is_f else " "
            h_str = "[#89b4fa]H[/]" if is_h else " "
            return f"[{g_str}{l_str}{f_str}{h_str}]"
        return ""

    def _get_tracking_label(self, d: dict[str, Any]) -> str:
        tracking_map = {
            "none": "[#a6e3a1]Says OK[/]",
            "limited": "[#f9e2af]Some[/]",
            "yes": "[#f38ba8]Tracking[/]",
            "unspecified": "[#6c7086]Unknown[/]",
        }
        val = str(d.get("tracking", ""))
        return tracking_map.get(val, val)

    def _get_latency_label(self, latency: float | None) -> str:
        if latency is None:
            return "[#f38ba8]ERR[/]"
        if latency < 150:
            return f"[#a6e3a1]{latency:.0f} ms[/]"
        if latency < 400:
            return f"[#f9e2af]{latency:.0f} ms[/]"
        return f"[#f38ba8]{latency:.0f} ms[/]"

    async def ping_rpc(self, client: httpx.AsyncClient, item: dict[str, Any]) -> None:
        url = item.get("actual_url", "")
        if not url or "${API_KEY}" in url or "{{secret:" in url:
            item["latency"] = None
            return

        start = time.time()
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1,
            }
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                item["latency"] = latency
            else:
                item["latency"] = None
        except Exception:
            item["latency"] = None

    def action_retry(self) -> None:
        self.run_worker(self.refresh_rpcs())

    def _get_selected_rpc(self) -> dict[str, Any] | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        try:
            # Get index from the row key
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            row_val = row_key.value
            if row_val is None:
                return None
            idx = int(row_val)
            return self.current_sorted_rpcs[idx]
        except (ValueError, TypeError, AttributeError, IndexError):
            return None

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        item = self._get_selected_rpc()
        if not item:
            return

        if item.get("needs_password"):
            self.picker_app.push_screen(
                PasswordModal(), lambda p: self._on_password_provided(item, p)
            )
        else:
            url = item.get("actual_url", "")
            self.dismiss(url)

    def _on_password_provided(self, item: dict[str, Any], password: str | None) -> None:
        if not password:
            return

        cm = self.picker_app.config
        rpc_id = item.get("id")
        if not rpc_id:
            return

        secret_data = cm.load_rpc_secret(rpc_id, password=password)

        if secret_data.get("status") == "ok":
            key = secret_data.get("api_key", "")
            url = item.get("url", "")
            final_url = cm.resolve_url_secrets(url, rpc_id, key)
            self.dismiss(final_url)
        elif secret_data.get("status") == "wrong_password":
            self.picker_app.notify("Wrong password", severity="error")
        else:
            self.picker_app.notify("Error loading secret", severity="error")

    def action_toggle_favorite(self) -> None:
        """Toggle favorite for the selected RPC (local)."""
        selected = self._get_selected_rpc()
        if selected:
            url = selected.get("url")
            if url:
                self.picker_app.config.toggle_favorite_rpc(url, is_global=False)
                self.update_table()

    def action_toggle_global_favorite(self) -> None:
        """Toggle favorite for the selected RPC (global)."""
        selected = self._get_selected_rpc()
        if selected:
            url = selected.get("url")
            if url:
                self.picker_app.config.toggle_favorite_rpc(url, is_global=True)
                self.update_table()
