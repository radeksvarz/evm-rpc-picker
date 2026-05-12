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
from .add_rpc_modal import AddRPCModal
from .password_modal import PasswordModal


class RPCScreen(Screen[str]):
    """Screen to select RPC and check latency."""

    app: "ChainRPCPicker"

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
        Binding("escape", "dismiss(None)", "Back"),
        Binding("a", "add_rpc", "Add Custom"),
        Binding("v", "paste_rpc", "Paste"),
        Binding("e", "edit_rpc", "Edit"),
        Binding("r", "retry", "Retry"),
        Binding("enter", "submit", "Select", tooltip="Select the highlighted RPC"),
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
        return rpcs

    def _gather_public_rpcs(self) -> list[dict[str, Any]]:
        rpcs: list[dict[str, Any]] = []
        raw_rpc = self.chain.get("rpc", [])
        for r in raw_rpc:
            url = None
            tracking = "unspecified"
            if isinstance(r, str):
                url = r
            elif isinstance(r, dict):
                url = r.get("url")
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
        cm = self.app.config
        cid = self.chain.get("chainId")
        if cid is None:
            return rpcs

        custom = cm.get_custom_rpcs(int(cid))
        for c in custom:
            url = c.get("url", "")
            is_encrypted = c.get("encrypted", False)
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
                        final_url = url.replace("${API_KEY}", key)
            else:
                # Locked
                display_url = url.replace("${API_KEY}", "********")

            rpcs.append(
                {
                    "id": rpc_id,
                    "url": final_url,
                    "display_url": display_url,
                    "tracking": "none",
                    "source": c.get("source", "global"),
                    "is_secret": has_secrets,
                    "needs_password": needs_password,
                    "note": c.get("note", ""),
                    "encrypted": c.get("encrypted", False),
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
                        "url": f_url,
                        "display_url": f_url,
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

        yield CustomHeader(f"Ξ EVM RPC Picker / {name}")
        with Horizontal(id="rpc-header"):
            yield Label(
                f"ID: {cid} | Short: {short} | Currency: {native}",
                id="header-left",
            )
            yield Label(f"{info_url}", id="header-right")

        table: DataTable = DataTable(id="rpc-table", cursor_type="row")
        yield table
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "URL", "Privacy", "Latency")
        await self.refresh_rpcs()

    async def refresh_rpcs(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

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

        # Sort by latency (None at the end)
        self.current_sorted_rpcs = sorted(
            items, key=lambda x: (x["latency"] is None, x["latency"] or 9999)
        )

        table = self.query_one(DataTable)
        table.clear()

        for i, d in enumerate(self.current_sorted_rpcs):
            url_display = d.get("display_url", "")
            if d.get("is_secret"):
                url_display = f"🔒 {url_display}"

            source = d.get("source", "")
            is_g = source == "global"
            is_l = source == "local"
            is_f = source == "foundry"
            is_h = source == "hardhat"

            if any([is_g, is_l, is_f, is_h]):
                g_str = "[#89b4fa]G[/]" if is_g else " "
                l_str = "[#89b4fa]L[/]" if is_l else " "
                f_str = "[#89b4fa]F[/]" if is_f else " "
                h_str = "[#89b4fa]H[/]" if is_h else " "
                indicator = f"[{g_str}{l_str}{f_str}{h_str}]"
            else:
                indicator = ""

            tracking_map = {
                "none": "[#a6e3a1]✅ None[/]",
                "limited": "[#f9e2af]⚠️ Limited[/]",
                "tracking": "[#f38ba8]❌ Tracking[/]",
                "unspecified": "[#6c7086]❔ Unknown[/]",
            }
            tracking_str = tracking_map.get(d.get("tracking", ""), str(d.get("tracking", "")))

            latency = d.get("latency")
            if latency is None:
                lat_str = "[#f38ba8]ERR[/]"
            elif latency < 150:
                lat_str = f"[#a6e3a1]{latency:.0f} ms[/]"
            elif latency < 400:
                lat_str = f"[#f9e2af]{latency:.0f} ms[/]"
            else:
                lat_str = f"[#f38ba8]{latency:.0f} ms[/]"

            table.add_row(indicator, url_display, tracking_str, lat_str, key=str(i))

        if table.row_count > 0:
            table.focus()

    async def ping_rpc(self, client: httpx.AsyncClient, item: dict[str, Any]) -> None:
        url = item.get("actual_url", "")
        if not url or "${API_KEY}" in url:
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

    def action_add_rpc(self) -> None:
        """Open the modal to add a custom RPC."""
        self.app.push_screen(
            AddRPCModal(self.chain.get("name", "Unknown"), self.chain.get("chainId", 0)),
            self._on_rpc_added,
        )

    def action_paste_rpc(self) -> None:
        """Open the modal with current clipboard (planned)."""
        self.action_add_rpc()

    def _on_rpc_added(self, data: dict[str, Any] | None) -> None:
        if not data:
            return

        cm = self.app.config
        # Default to local if it exists, otherwise global
        is_global = not cm.local_config_exists()

        cid = self.chain.get("chainId")
        if cid is not None:
            cm.add_custom_rpc(int(cid), data, is_global=is_global)
        self.app.notify("Custom RPC added", title="Success")

        self.rpc_data = self._gather_rpcs()
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

    def action_edit_rpc(self) -> None:
        """Edit the highlighted custom RPC."""
        item = self._get_selected_rpc()
        if not item:
            return

        if not item.get("id"):
            self.app.notify("Only custom RPCs can be edited", severity="warning")
            return

        initial_data: dict[str, Any] = {
            "url": item.get("url"),
            "note": item.get("note", ""),
            "encrypted": item.get("encrypted", False),
        }

        if item.get("is_secret"):
            if item.get("encrypted"):
                self.app.push_screen(
                    PasswordModal(),
                    lambda p: self._on_password_for_edit(item, initial_data, p),
                )
            else:
                self._on_password_for_edit(item, initial_data, None)
        else:
            self._open_edit_modal(item, initial_data)

    def _on_password_for_edit(
        self, item: dict[str, Any], initial_data: dict[str, Any], password: str | None
    ) -> None:
        if item.get("encrypted") and not password:
            return

        rpc_id = item.get("id")
        if not rpc_id:
            return

        secrets = self.app.config.load_rpc_secret(rpc_id, password)
        if secrets["status"] == "ok":
            initial_data["secret_note"] = secrets.get("secret_note", "")
            if secrets.get("api_key"):
                initial_data["url"] = f"{initial_data['url']}/{secrets['api_key']}"

            self._open_edit_modal(item, initial_data)
        elif secrets["status"] == "wrong_password":
            self.app.notify("Wrong password", severity="error")

    def _open_edit_modal(self, item: dict[str, Any], initial_data: dict[str, Any]) -> None:
        self.app.push_screen(
            AddRPCModal(
                self.chain.get("name", "Unknown"),
                int(self.chain.get("chainId", 0)),
                initial_data,
            ),
            lambda d: self._handle_edit_result(item, d),
        )

    def _handle_edit_result(self, item: dict[str, Any], data: dict[str, Any] | None) -> None:
        if not data:
            return

        rpc_id = item.get("id")
        if not rpc_id:
            return

        is_global = item.get("source") == "global"
        self.app.config.update_custom_rpc(
            int(self.chain.get("chainId", 0)), rpc_id, data, is_global=is_global
        )
        self.app.notify("RPC updated")
        self.rpc_data = self._gather_rpcs()
        self.run_worker(self.refresh_rpcs())

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        item = self._get_selected_rpc()
        if not item:
            return

        if item.get("needs_password"):
            self.app.push_screen(PasswordModal(), lambda p: self._on_password_provided(item, p))
        else:
            url = item.get("actual_url", "")
            self.dismiss(url)

    def _on_password_provided(self, item: dict[str, Any], password: str | None) -> None:
        if not password:
            return

        cm = self.app.config
        rpc_id = item.get("id")
        if not rpc_id:
            return

        secret_data = cm.load_rpc_secret(rpc_id, password=password)

        if secret_data.get("status") == "ok":
            key = secret_data.get("api_key", "")
            url = item.get("url", "")
            final_url = url.replace("********", key)
            self.dismiss(final_url)
        elif secret_data.get("status") == "wrong_password":
            self.app.notify("Wrong password", severity="error")
        else:
            self.app.notify("Error loading secret", severity="error")
