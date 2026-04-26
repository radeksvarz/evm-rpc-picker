import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker

import httpx
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListView

from ..context import ContextDetector
from ..widgets import RPCListItem
from .add_rpc_modal import AddRPCModal
from .password_modal import PasswordModal


class RPCScreen(ModalScreen[str]):
    """Screen to select RPC and check latency."""

    app: "ChainRPCPicker"

    DEFAULT_CSS = """
    RPCScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #rpc-container {
        width: 80%;
        height: 80%;
        background: #1e1e2e;
        border: thick #89b4fa;
        padding: 1;
    }

    #rpc-header {
        height: auto;
        width: 100%;
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

    #rpc-list {
        height: 1fr;
        border: solid #313244;
        background: #181825;
        margin: 1 0;
    }

    .url-label {
        width: 1fr;
    }

    #rpc-footer {
        height: auto;
        align: center middle;
    }

    .button-row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    RPCListItem, RPCListItem > Horizontal {
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0 1;
    }

    RPCListItem:hover {
        background: #313244;
    }

    RPCListItem.--highlight {
        background: #89b4fa 30%;
    }

    Button {
        margin: 0 1;
        background: #313244;
        color: #cdd6f4;
        border: none;
    }

    Button:hover {
        background: #45475a;
    }

    #btn-select {
        color: #a6e3a1;
    }

    #btn-back {
        color: #f38ba8;
    }
    """
    BINDINGS = [
        ("escape", "dismiss(None)", "Back"),
        ("a", "add_rpc", "Add Custom"),
        ("v", "paste_rpc", "Paste"),
        ("e", "edit_rpc", "Edit"),
        ("r", "retry", "Retry"),
        ("enter", "submit", "Select"),
    ]

    def __init__(self, chain: dict[str, Any]):
        super().__init__()
        self.chain = chain
        self.rpc_data: list[dict[str, Any]] = self._gather_rpcs()

    def _gather_rpcs(self) -> list[dict[str, Any]]:
        rpcs = []
        cm = self.app.config

        # 1. Public RPCs
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

        # 2. Custom RPCs from config
        cid = self.chain.get("chainId")
        if cid is not None:
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
                    }
                )

        # 3. Context RPCs (Foundry)
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
                        "source": "project",
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

        with Container(id="rpc-container"):
            with Horizontal(id="rpc-header"):
                yield Label(
                    f"[bold #89b4fa]{name}[/bold #89b4fa] (ID: {cid}, "
                    f"Short: {short}, Currency: {native})",
                    id="header-left",
                )
                info_url = self.chain.get("infoURL", "")
                yield Label(f"{info_url}", id="header-right")
            yield ListView(id="rpc-list")
            with Horizontal(classes="button-row"):
                yield Button("[u]B[/u]ack [ESC]", id="btn-back", variant="error")
                yield Button("[u]R[/u]etry", id="btn-retry")
                yield Button("[u]S[/u]elect [⏎]", id="btn-select", variant="success")

    async def on_mount(self) -> None:
        await self.refresh_rpcs()

    async def refresh_rpcs(self) -> None:
        rpc_list = self.query_one("#rpc-list", ListView)
        rpc_list.clear()

        items = []
        for r in self.rpc_data:
            item = RPCListItem(
                r["url"],
                tracking=r["tracking"],
                source=r["source"],
                is_secret=r["is_secret"],
            )
            items.append(item)
            rpc_list.append(item)

        # Run latency checks in background
        self.run_worker(self.check_latencies(items))

    async def check_latencies(self, items: list[RPCListItem]) -> None:
        async with httpx.AsyncClient(timeout=2.5) as client:
            tasks = [self.ping_rpc(client, item) for item in items]
            await asyncio.gather(*tasks)

        # Sort by latency
        rpc_list = self.query_one("#rpc-list", ListView)
        # Get data from current items before clearing
        items_data = []
        for item in items:
            items_data.append(
                {
                    "display_url": item.url,
                    "latency": item.latency,
                    "tracking": item.tracking,
                    "source": item.source,
                    "is_secret": item.is_secret,
                    "actual_url": item.actual_url,
                    "needs_password": item.needs_password,
                    "rpc_id": item.rpc_id,
                    "note": item.note,
                    "encrypted": item.encrypted,
                }
            )

        sorted_data = sorted(items_data, key=lambda x: (x["latency"] is None, x["latency"] or 9999))

        rpc_list.clear()
        for d in sorted_data:
            new_item = RPCListItem(
                str(d["display_url"]),
                tracking=str(d["tracking"]),
                source=str(d["source"]),
                is_secret=bool(d["is_secret"]),
            )
            new_item.actual_url = str(d["actual_url"])
            new_item.needs_password = bool(d["needs_password"])
            new_item.rpc_id = cast(str | None, d["rpc_id"])
            new_item.note = str(d.get("note", ""))
            new_item.encrypted = bool(d.get("encrypted", False))
            new_item.has_secrets = bool(d.get("is_secret", False))

            rpc_list.append(new_item)
            new_item.update_latency(cast(float | None, d["latency"]))

        if rpc_list.children:
            rpc_list.index = 0
            rpc_list.focus()

    async def ping_rpc(self, client: httpx.AsyncClient, item: RPCListItem) -> None:
        url = getattr(item, "actual_url", item.url)
        if not url or "${API_KEY}" in url:
            item.update_latency(None)
            return

        start = time.time()
        try:
            # Simple JSON-RPC call to check latency
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1,
            }
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                item.update_latency(latency)
            else:
                item.update_latency(None)
        except Exception:
            item.update_latency(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.dismiss(None)
        elif event.button.id == "btn-retry":
            self.action_retry()
        elif event.button.id == "btn-select":
            self.action_submit()

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

    def _on_rpc_added(self, data: dict | None) -> None:
        if not data:
            return

        cm = self.app.config
        # Default to local if it exists, otherwise global
        is_global = not cm.local_config_exists()

        cid = self.chain.get("chainId")
        if cid is not None:
            cm.add_custom_rpc(int(cid), data, is_global=is_global)
        self.app.notify("Custom RPC added", title="Success")

        # Refresh the screen data and UI
        self.rpc_data = self._gather_rpcs()
        self.run_worker(self.refresh_rpcs())

    def action_edit_rpc(self) -> None:
        """Edit the highlighted custom RPC."""
        rpc_list = self.query_one(ListView)
        if not rpc_list.highlighted_child:
            return

        item = rpc_list.highlighted_child
        if not isinstance(item, RPCListItem) or not item.rpc_id:
            self.app.notify("Only custom RPCs can be edited", severity="warning")
            return

        # Prepare initial data
        initial_data: dict[str, Any] = {
            "url": item.url,
            "note": item.note,
            "encrypted": item.encrypted,
        }

        # If it has secrets, we need to load them
        if item.has_secrets:
            if item.encrypted:
                # Ask for password first
                self.app.push_screen(
                    PasswordModal(),
                    lambda p: self._on_password_for_edit(item, initial_data, p),
                )
            else:
                self._on_password_for_edit(item, initial_data, None)
        else:
            self._open_edit_modal(item, initial_data)

    def _on_password_for_edit(
        self, item: RPCListItem, initial_data: dict[str, Any], password: str | None
    ) -> None:
        if item.encrypted and not password:
            return

        if not item.rpc_id:
            return

        secrets = self.app.config.load_rpc_secret(item.rpc_id, password)
        if secrets["status"] == "ok":
            initial_data["secret_note"] = secrets.get("secret_note", "")
            # If the original URL was base URL, restore full URL with key
            if secrets.get("api_key"):
                initial_data["url"] = f"{initial_data['url']}/{secrets['api_key']}"

            self._open_edit_modal(item, initial_data)
        elif secrets["status"] == "wrong_password":
            self.app.notify("Wrong password", severity="error")

    def _open_edit_modal(self, item: RPCListItem, initial_data: dict[str, Any]) -> None:
        self.app.push_screen(
            AddRPCModal(
                self.chain.get("name", "Unknown"),
                int(self.chain.get("chainId", 0)),
                initial_data,
            ),
            lambda d: self._handle_edit_result(item, d),
        )

    def _handle_edit_result(self, item: RPCListItem, data: dict[str, Any] | None) -> None:
        if not data:
            return

        if not item.rpc_id:
            return

        is_global = item.source == "global"
        self.app.config.update_custom_rpc(
            int(self.chain.get("chainId", 0)), item.rpc_id, data, is_global=is_global
        )
        self.app.notify("RPC updated")
        self.run_worker(self.refresh_rpcs())

    @on(ListView.Selected)
    def on_rpc_selected_list(self, event: ListView.Selected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        rpc_list = self.query_one("#rpc-list", ListView)
        if rpc_list.highlighted_child:
            item = rpc_list.highlighted_child
            if not isinstance(item, RPCListItem):
                return
            if item.needs_password:
                self.app.push_screen(PasswordModal(), lambda p: self._on_password_provided(item, p))
            else:
                url = item.actual_url
                self.dismiss(url)

    def _on_password_provided(self, item: RPCListItem, password: str | None) -> None:
        if not password:
            return

        cm = self.app.config
        if not item.rpc_id:
            return
        secret_data = cm.load_rpc_secret(item.rpc_id, password=password)

        if secret_data.get("status") == "ok":
            key = secret_data.get("api_key", "")
            final_url = item.url.replace("********", key)
            self.dismiss(final_url)
        elif secret_data.get("status") == "wrong_password":
            self.app.notify("Wrong password", severity="error")
        else:
            self.app.notify("Error loading secret", severity="error")

    def on_key(self, event: Any) -> None:
        # Handled by BINDINGS
        pass
