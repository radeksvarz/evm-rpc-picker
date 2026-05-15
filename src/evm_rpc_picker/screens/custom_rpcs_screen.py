import subprocess
from typing import TYPE_CHECKING, Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..widgets.custom_header import CustomHeader
from .add_rpc_modal import AddRPCModal
from .confirm_modal import ConfirmModal

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


class CustomRPCScreen(Screen[str]):
    """Screen to manage all custom RPCs."""

    app: "ChainRPCPicker"

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "add_rpc", "Add Custom RPC"),
        Binding("e", "edit_rpc", "Edit RPC"),
        Binding("delete", "delete_rpc", "Delete RPC"),
        Binding("ctrl+v", "paste_add_rpc", "Paste & Add"),
        Binding("ctrl+b", "toggle_favorite_rpc", "Toggle Favorite"),
        Binding("enter", "submit", "Select RPC", tooltip="Select the highlighted RPC"),
    ]

    def compose(self) -> ComposeResult:
        yield CustomHeader("Ξ EVM RPC Picker / Custom RPCs")
        self.table = CustomRPCTable(id="custom-rpcs-table", cursor_type="row")
        yield self.table
        yield Footer()

    def on_mount(self) -> None:
        self.table.add_columns("Src", "Name", "Type", "Chain ID", "URL", "Config Note", "Keyring Note")
        self.refresh_rpcs()

    def refresh_rpcs(self) -> None:
        self.table.clear()
        self.rpcs: list[dict[str, Any]] = []

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

        # Sort by chain ID
        self.rpcs.sort(key=lambda x: x["chain_id"])

        for i, rpc in enumerate(self.rpcs):
            cid = rpc["chain_id"]
            rpc_id = rpc["id"]
            url = rpc.get("url", "")

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

            if rpc.get("has_secrets"):
                url_display = f"🔒 {url_display}"
                secret_data = cfg.load_rpc_secret(rpc_id)
                if secret_data.get("status") == "needs_password":
                    keyring_note = "[#f38ba8]🔒 Locked[/]"
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
            row_val = row_key.value
            if row_val is None:
                return None
            idx = int(row_val)
            return self.rpcs[idx]
        except (ValueError, TypeError, AttributeError, IndexError):
            return None

    def action_toggle_favorite_rpc(self) -> None:
        """Toggle favorite status for the selected RPC."""
        selected = self._get_selected_rpc()
        if not selected:
            return
        
        is_global = selected["source"] == "global"
        # The url in selected is the final url if it doesn't have secrets.
        # Wait, selected["url"] has ${API_KEY} if it's locked.
        # But favorites uses the actual base url?
        url = selected.get("url", "")
        self.app.config.toggle_favorite_rpc(url, is_global=is_global)
        
        # It's better to refresh the table to show a favorite star if we add one, 
        # but right now custom rpcs don't show the star. Let's still refresh.
        self.refresh_rpcs()

    def action_add_rpc(self) -> None:
        """Add a new custom RPC."""
        self._open_add_modal()

    def action_paste_add_rpc(self) -> None:
        """Paste URL from clipboard and open add modal."""
        # Try internal app clipboard first
        clipboard = self.app.clipboard.strip()
        
        # Fallback to system clipboard (Wayland/X11)
        if not clipboard:
            try:
                # Try wl-paste (Wayland)
                clipboard = subprocess.check_output(["wl-paste"], text=True, stderr=subprocess.DEVNULL).strip()
            except Exception:
                try:
                    # Try xclip (X11)
                    clipboard = subprocess.check_output(
                        ["xclip", "-selection", "clipboard", "-o"], 
                        text=True, 
                        stderr=subprocess.DEVNULL
                    ).strip()
                except Exception:
                    pass

        if clipboard:
            self._open_add_modal({"url": clipboard})
        else:
            self.app.notify("Clipboard is empty (tried app and system)", severity="warning")
            self._open_add_modal()

    def _open_add_modal(self, initial_data: dict[str, Any] | None = None) -> None:
        """Internal helper to open the AddRPCModal."""
        def check_add(data: dict[str, Any] | None) -> None:
            if data is None:
                return

            chain_id = data.pop("chain_id")
            is_global = data.pop("is_global", False)

            self.app.config.add_custom_rpc(
                chain_id,
                data,
                is_global=is_global,
                password=data.get("password"),
            )
            self.app.notify("Custom RPC added", title="Success")
            self.refresh_rpcs()

        self.app.push_screen(AddRPCModal(initial_data=initial_data), check_add)

    def action_edit_rpc(self) -> None:
        selected = self._get_selected_rpc()
        if not selected:
            self.app.notify("No RPC selected", severity="warning")
            return

        is_global = selected["source"] == "global"
        rpc_id = selected["id"]
        chain_id = selected["chain_id"]

        # Load secrets if any
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
                from .password_modal import PasswordModal

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

        # If the original url didn't contain API_KEY, but there is an API key, we format it nicely
        api_key = secret_data.get("api_key")
        if api_key and "${API_KEY}" in initial_data["url"]:
            initial_data["url"] = initial_data["url"].replace("${API_KEY}", api_key)

        def check_edit(data: dict[str, Any] | None) -> None:
            if data is None:
                return
            # chain_id is popped because update_custom_rpc expects it separately
            if "chain_id" in data:
                data.pop("chain_id")

            self.app.config.update_custom_rpc(
                chain_id,
                rpc_id,
                data,
                is_global=is_global,
            )
            # update_custom_rpc handles deleting secrets if api_key and secret_note are empty.
            # wait, update_custom_rpc needs password handling. In config.py:
            # password = rpc_data.get("password")
            # This is correct.
            self.app.notify("Custom RPC updated", title="Success")
            self.refresh_rpcs()

        from ..models import get_cached_chains

        chains_data = get_cached_chains() or []

        # Find chain name
        chain_name = "Unknown"
        for c in chains_data:
            if c.get("chainId") == chain_id:
                chain_name = c.get("name", "Unknown")
                break

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

            chain_id = selected["chain_id"]
            rpc_id = selected["id"]
            is_global = selected["source"] == "global"

            cfg = self.app.config
            config = cfg.global_config if is_global else cfg.local_config
            path = cfg.GLOBAL_CONFIG_FILE if is_global else cfg.LOCAL_CONFIG_FILE

            cid_str = str(chain_id)
            custom_rpcs = config.get("custom_rpcs", {})
            if cid_str in custom_rpcs:
                rpcs = custom_rpcs[cid_str]
                rpcs = [r for r in rpcs if r["id"] != rpc_id]
                if not rpcs:
                    del custom_rpcs[cid_str]
                else:
                    custom_rpcs[cid_str] = rpcs

                config["custom_rpcs"] = custom_rpcs
                cfg._save_toml(path, config, is_global=is_global)

                # Delete secret
                cfg.delete_secret(rpc_id)

                self.app.notify("Custom RPC deleted", title="Success")
                self.refresh_rpcs()

        url = selected.get("url", "")
        source = selected.get("source", "global")
        source_str = "[#89b4fa]Global[/] Config" if source == "global" else "[#a6e3a1]Local Project[/] Config"

        msg = (
            f"Are you sure you want to delete this Custom RPC?\n\n"
            f"[bold]URL:[/] {url}\n"
            f"[bold]From:[/] {source_str}"
        )

        self.app.push_screen(
            ConfirmModal(msg, yes_label="Delete"),
            check_delete,
        )

    @on(DataTable.RowSelected)
    def on_rpc_selected_list(self, event: DataTable.RowSelected) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        item = self._get_selected_rpc()
        if not item:
            return

        if item.get("encrypted"):
            from .password_modal import PasswordModal

            self.app.push_screen(PasswordModal(), lambda p: self._on_password_provided(item, p))
        else:
            if item.get("has_secrets"):
                secret_data = self.app.config.load_rpc_secret(item["id"])
                if secret_data.get("status") == "ok":
                    key = secret_data.get("api_key", "")
                    url = item.get("url", "").replace("${API_KEY}", key)
                    self.dismiss(url)
                else:
                    self.app.notify("Error loading secret", severity="error")
            else:
                self.dismiss(item.get("url", ""))

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
            url = item.get("url", "").replace("${API_KEY}", key)
            self.dismiss(url)
        elif secret_data.get("status") == "wrong_password":
            self.app.notify("Wrong password", severity="error")
        else:
            self.app.notify("Error loading secret", severity="error")
