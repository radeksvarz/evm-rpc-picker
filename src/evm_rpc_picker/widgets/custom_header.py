from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class CustomHeader(Horizontal):
    """1-row header with icon, title and subtitle instead of clock."""

    DEFAULT_CSS = """
    CustomHeader {
        height: 1;
        background: #313244;
        color: #cdd6f4;
        padding: 0 2;
        text-style: bold;
    }
    #header-title {
        width: auto;
    }
    #header-subtitle {
        width: 1fr;
        text-align: right;
        text-style: italic;
        color: #9399b2;
    }
    """

    def __init__(self, title: str = "Ξ EVM RPC Picker", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._header_title = title

    def compose(self) -> ComposeResult:
        yield Label(self._header_title, id="header-title")
        yield Label("CU @ 🍻 BeerFi Prague", id="header-subtitle")

    def on_click(self) -> None:
        """Open the command palette when the header is clicked."""
        self.app.action_command_palette()
