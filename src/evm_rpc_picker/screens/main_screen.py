import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..tui import ChainRPCPicker

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Tabs

from ..commands import RefreshDataProvider
from ..tabs.chainlist_tab import ChainlistTab
from ..tabs.custom_rpcs_tab import CustomRPCTab
from ..tabs.favorite_rpcs_tab import FavoriteRPCTab
from ..widgets import CustomHeader, EnvStatus


class MainScreen(Screen[str]):
    """Main screen shell hosting navigation tabs and content switcher."""

    app: "ChainRPCPicker"

    COMMANDS = Screen.COMMANDS | {RefreshDataProvider}

    DEFAULT_CSS = """
    #main-content-switcher {
        height: 1fr;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "app.quit", "Cancel", tooltip="Quit the RPC picker"),
        Binding("ctrl+n", "switch_tab('tab-chainlist')", "Chainlist.org Tab", show=False),
        Binding("ctrl+u", "switch_tab('tab-personal')", "Personal RPC URLs Tab", show=False),
        Binding("ctrl+b", "switch_tab('tab-favorites')", "Favorite RPCs Tab", show=False),
        Binding(
            "ctrl+r",
            "refresh_all_data",
            "Refresh Data",
            tooltip="from Chainlist.org",
            show=False,
        ),
        Binding("ctrl+e", "use_current_env", "Use Current ETH_RPC_URL", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield CustomHeader(show_tabs=True)
        with ContentSwitcher(initial="tab-chainlist", id="main-content-switcher"):
            yield ChainlistTab(id="tab-chainlist")
            yield CustomRPCTab(id="tab-personal")
            yield FavoriteRPCTab(id="tab-favorites")
        yield EnvStatus(id="env-status-widget")
        yield Footer()

    async def action_refresh_all_data(self) -> None:
        """Refresh data in active tab and check ENV latency."""
        with contextlib.suppress(Exception):
            env_status = self.query_one(EnvStatus)
            if env_status.current_rpc:
                env_status.latency_label.update("--- ms")
                env_status.check_latency()

        self.action_delegate_to_tab("refresh_data")

    @on(Tabs.TabActivated)
    def on_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Switch content when tab is activated and focus its table."""
        switcher = self.query_one("#main-content-switcher", ContentSwitcher)
        if event.tab.id:
            switcher.current = event.tab.id

            # Refresh data in the activated tab
            with contextlib.suppress(Exception):
                tab_content = self.query_one(f"#{event.tab.id}")
                if hasattr(tab_content, "load_data"):
                    tab_content.load_data()
                elif hasattr(tab_content, "refresh_rpcs"):
                    tab_content.refresh_rpcs()

            # Use call_after_refresh to ensure the new tab is rendered before focusing
            def focus_new_tab() -> None:
                with contextlib.suppress(Exception):
                    # Find the newly activated tab by ID
                    tab_content = self.query_one(f"#{event.tab.id}")
                    # Look for a DataTable inside it
                    from textual.widgets import DataTable

                    table = tab_content.query(DataTable).first()
                    if table:
                        table.focus()

            self.call_after_refresh(focus_new_tab)

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch tab programmatically."""
        tabs = self.query_one(Tabs)
        tabs.active = tab_id

    def action_delegate_to_tab(self, method_name: str) -> None:
        """Delegate an action to the currently active tab."""
        switcher = self.query_one("#main-content-switcher", ContentSwitcher)
        if not switcher.current:
            return
        active_tab = self.query_one(f"#{switcher.current}")
        if active_tab and hasattr(active_tab, method_name):
            method = getattr(active_tab, method_name)
            import asyncio

            if asyncio.iscoroutinefunction(method):
                self.run_worker(method())
            else:
                method()

    def action_use_current_env(self) -> None:
        """Exit with current ETH_RPC_URL if available."""
        # This is usually only relevant in ChainlistTab, but we can check across.
        from ..widgets.env_status import EnvStatus

        try:
            env_status = self.query_one(EnvStatus)
            if env_status.current_rpc:
                self.app.exit(env_status.current_rpc)
            else:
                self.app.notify("ETH_RPC_URL is not set", severity="warning")
        except Exception:
            self.app.notify("Current environment not available in this view", severity="error")

    def _on_rpc_selected(self, rpc_url: str | None) -> None:
        """Common callback for when any tab or sub-screen selects an RPC."""
        if rpc_url:
            self.app.exit(rpc_url)
