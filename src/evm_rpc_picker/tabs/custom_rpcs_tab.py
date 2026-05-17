import contextlib
import subprocess
from typing import TYPE_CHECKING, Any, cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from ..screens.add_rpc_modal import AddRPCModal
from ..screens.confirm_modal import ConfirmModal

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker


class CustomRPCTable(DataTable[Any]):
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


class CustomRPCTab(Static):
    """Tab to manage all custom RPCs."""

    app: "ChainRPCPicker"

    BINDINGS = [
        Binding("a", "add_rpc", "Add RPC", show=True),
        Binding("e", "edit_rpc", "Edit RPC", show=True),
        Binding("delete", "delete_rpc", "Delete RPC", show=True),
        Binding("ctrl+v", "paste_add_rpc", "Paste & Add", show=True),
        Binding("ctrl+b", "toggle_favorite_rpc", "Toggle Favorite", show=True),
    ]

    def compose(self) -> ComposeResult:
        self.table = CustomRPCTable(id="custom-rpcs-table", cursor_type="row")
        yield self.table

    def on_mount(self) -> None:
        self.table.add_columns(
            "Src", "Name", "Type", "Chain ID", "URL", "Config Note", "Keyring Note"
        )
        self.refresh_rpcs()

    def refresh_rpcs(self) -> None:
        self._load_rpcs()
        self._render_rpcs()

    def _load_rpcs(self) -> None:
        self.rpcs = []
        cfg = self.app.config

        # Load local
        local_rpcs = cfg.local_config.get("custom_rpcs", {})
        for cid_str, rpcs in local_rpcs.items():
            for rpc in rpcs:
                item = dict(rpc)
                item["source"] = "local"
                item["chain_id"] = int(cid_str)
                self.rpcs.append(item)

        # Load global
        global_rpcs = cfg.global_config.get("custom_rpcs", {})
        for cid_str, rpcs in global_rpcs.items():
            for rpc in rpcs:
                item = dict(rpc)
                item["source"] = "global"
                item["chain_id"] = int(cid_str)
                self.rpcs.append(item)

        self.rpcs.sort(key=lambda x: x["chain_id"])

    def _render_rpcs(self) -> None:
        self.table.clear()
        cfg = self.app.config

        for i, rpc in enumerate(self.rpcs):
            cid = rpc["chain_id"]
            rpc_id = rpc["id"]
            url = rpc.get("url", "").strip()
            is_g = rpc["source"] == "global"
            src_str = "[#89b4fa]G[/]" if is_g else "[#89b4fa]L[/]"

            is_fav = False
            if is_g:
                is_fav = url in cfg.global_config.get("favorite_rpcs", [])
            else:
                is_fav = url in cfg.local_config.get("favorite_rpcs", [])

            fav_str = "[#f9e2af]★[/]" if is_fav else " "
            ind = f"[{src_str} {fav_str} ]"

            url_display = url
            network_type = rpc.get("network_type", "Production")
            config_note = rpc.get("note", "")
            keyring_note = ""

            if rpc.get("encrypted"):
                url_display = f"🔑🔒 {url_display}"
            elif rpc.get("has_secrets"):
                url_display = f"🔒 {url_display}"

            if rpc.get("has_secrets"):
                secret_data = cfg.load_rpc_secret(rpc_id)
                if secret_data.get("status") == "needs_password":
                    keyring_note = "[#f38ba8]🔑🔒 Locked[/]"
                else:
                    keyring_note = secret_data.get("secret_note", "")

            rpc_name = rpc.get("name", "")
            self.table.add_row(
                ind,
                rpc_name,
                network_type,
                str(cid),
                url_display,
                config_note,
                keyring_note,
                key=str(i),
            )

        if self.table.row_count > 0:
            self.table.focus()

    def _get_selected_rpc(self) -> dict[str, Any] | None:
        if not self.table.row_count:
            return None
        try:
            row_key = self.table.coordinate_to_cell_key(self.table.cursor_coordinate).row_key
            idx = int(str(row_key.value))
            return cast(dict[str, Any], self.rpcs[idx])
        except (ValueError, TypeError, AttributeError, IndexError):
            return None

    def action_toggle_favorite_rpc(self) -> None:
        selected = self._get_selected_rpc()
        if not selected:
            return
        is_global = selected["source"] == "global"
        self.app.config.toggle_favorite_rpc(selected.get("url", ""), is_global=is_global)
        self.refresh_rpcs()

    def action_add_rpc(self) -> None:
        self._open_add_modal()

    def action_paste_add_rpc(self) -> None:
        clipboard = ""
        import shutil

        wl_paste = shutil.which("wl-paste")
        xclip = shutil.which("xclip")

        # Try Wayland
        if wl_paste:
            with contextlib.suppress(Exception):
                clipboard = subprocess.check_output(  # noqa: S603
                    [wl_paste], text=True, stderr=subprocess.DEVNULL
                ).strip()

        # If Wayland fails or empty, try X11
        if not clipboard and xclip:
            with contextlib.suppress(Exception):
                clipboard = subprocess.check_output(  # noqa: S603
                    [xclip, "-selection", "clipboard", "-o"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()

        if not clipboard:
            clipboard = self.app.clipboard.strip()

        if clipboard:
            self._open_add_modal({"url": clipboard})
        else:
            self.app.notify("Clipboard is empty", severity="warning")
            self._open_add_modal()

    def _open_add_modal(self, initial_data: dict[str, Any] | None = None) -> None:
        def check_add(data: dict[str, Any] | None) -> None:
            if data is None:
                return
            chain_id = data.pop("chain_id")
            is_global = data.pop("is_global", False)
            self.app.config.add_custom_rpc(
                chain_id, data, is_global=is_global, password=data.get("password")
            )
            self.app.notify("Custom RPC added", title="Success")
            self.refresh_rpcs()

        self.app.push_screen(AddRPCModal(initial_data=initial_data), check_add)

    def action_edit_rpc(self) -> None:
        selected = self._get_selected_rpc()
        if not selected:
            return

        is_global = selected["source"] == "global"
        rpc_id = selected["id"]
        chain_id = selected["chain_id"]

        if selected.get("has_secrets"):

            def check_password(password: str | None) -> None:
                if password is None:
                    return
                secret_data = self.app.config.load_rpc_secret(rpc_id, password)
                if secret_data.get("status") == "wrong_password":
                    self.app.notify("Invalid password", severity="error")
                    return
                self._open_edit_modal(selected, secret_data, is_global, rpc_id, chain_id)

            if selected.get("encrypted"):
                from ..screens.password_modal import PasswordModal

                self.app.push_screen(PasswordModal(), check_password)
                return
            else:
                secret_data = self.app.config.load_rpc_secret(rpc_id)
                self._open_edit_modal(selected, secret_data, is_global, rpc_id, chain_id)
        else:
            self._open_edit_modal(selected, {}, is_global, rpc_id, chain_id)

    def _open_edit_modal(
        self,
        selected: dict[str, Any],
        secret_data: dict[str, Any],
        is_global: bool,
        rpc_id: str,
        chain_id: int,
    ) -> None:
        initial_data = {
            "name": selected.get("name", ""),
            "url": selected.get("url", ""),
            "network_type": selected.get("network_type", "Production"),
            "note": selected.get("note", ""),
            "secret_note": secret_data.get("secret_note", ""),
            "encrypted": selected.get("encrypted", False),
        }
        api_key = secret_data.get("api_key")
        if api_key and "${API_KEY}" in initial_data["url"]:
            initial_data["url"] = initial_data["url"].replace("${API_KEY}", api_key)

        def check_edit(data: dict[str, Any] | None) -> None:
            if data is None:
                return
            if "chain_id" in data:
                data.pop("chain_id")
            self.app.config.update_custom_rpc(chain_id, rpc_id, data, is_global=is_global)
            self.app.notify("Custom RPC updated", title="Success")
            self.refresh_rpcs()

        from ..models import get_cached_chains

        chains_data = get_cached_chains() or []
        chain_name = next(
            (c.get("name", "Unknown") for c in chains_data if c.get("chainId") == chain_id),
            "Unknown",
        )
        self.app.push_screen(
            AddRPCModal(chain_name=chain_name, chain_id=chain_id, initial_data=initial_data),
            check_edit,
        )

    def action_delete_rpc(self) -> None:
        selected = self._get_selected_rpc()
        if not selected:
            return

        def check_delete(confirm: bool | None) -> None:
            if not confirm:
                return
            self.app.config.delete_custom_rpc(
                selected["chain_id"], selected["id"], is_global=(selected["source"] == "global")
            )
            self.app.notify("Custom RPC deleted", title="Success")
            self.refresh_rpcs()

        msg = (
            "Are you sure you want to delete this Custom RPC?\n\n"
            f"[bold]URL:[/] {selected.get('url')}"
        )
        self.app.push_screen(ConfirmModal(msg, yes_label="Delete"), check_delete)

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        item = self._get_selected_rpc()
        if not item:
            return

        if item.get("encrypted"):
            from ..screens.password_modal import PasswordModal

            self.app.push_screen(PasswordModal(), lambda p: self._on_password_provided(item, p))
        else:
            if item.get("has_secrets"):
                secret_data = self.app.config.load_rpc_secret(item["id"])
                if secret_data.get("status") == "ok":
                    url = item.get("url", "").replace("${API_KEY}", secret_data.get("api_key", ""))
                    self._on_url_ready(url)
                else:
                    self.app.notify("Error loading secret", severity="error")
            else:
                self._on_url_ready(item.get("url", ""))

    def _on_password_provided(self, item: dict[str, Any], password: str | None) -> None:
        if not password:
            return
        secret_data = self.app.config.load_rpc_secret(item["id"], password=password)
        if secret_data.get("status") == "ok":
            url = item.get("url", "").replace("${API_KEY}", secret_data.get("api_key", ""))
            self._on_url_ready(url)
        elif secret_data.get("status") == "wrong_password":
            self.app.notify("Wrong password", severity="error")
        else:
            self.app.notify("Error loading secret", severity="error")

    def _on_url_ready(self, url: str) -> None:
        # We need to call the callback that MainScreen expects
        if hasattr(self.app.screen, "_on_rpc_selected"):
            self.app.screen._on_rpc_selected(url)
