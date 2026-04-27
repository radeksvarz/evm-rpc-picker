"""Widget to display the active configuration context."""

from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Horizontal
from ..context import ContextDetector

class ContextBar(Horizontal):
    """Bar displaying the active configuration context (Global, Local, Foundry, Hardhat)."""

    DEFAULT_CSS = """
    ContextBar {
        background: transparent;
        height: 1;
        width: 100%;
        padding: 0 2;
        content-align: right middle;
    }

    #context-spacer {
        width: 1fr;
    }

    .context-label {
        color: #9399b2;
        margin-right: 2;
    }

    .context-indicator {
        margin-right: 2;
    }

    .status-on {
        color: #89b4fa; /* Bright Blue/Cyan */
        text-style: bold;
    }

    .status-off {
        color: #45475a; /* Dim Grey */
    }

    .status-text-on {
        color: #cdd6f4; /* Bright White */
    }

    .status-text-off {
        color: #45475a; /* Dim Grey */
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="context-spacer")
        yield Label("Context:", id="context-title", classes="context-label")
        
        # We will update these in on_mount
        self.gbl = Label("○ GLOBAL", classes="context-indicator status-off")
        self.loc = Label("○ LOCAL", classes="context-indicator status-off")
        self.fdy = Label("○ FOUNDRY", classes="context-indicator status-off")
        self.hdh = Label("○ HARDHAT", classes="context-indicator status-off")
        
        yield self.gbl
        yield self.loc
        yield self.fdy
        yield self.hdh

    def on_mount(self) -> None:
        self.update_status()

    def update_status(self) -> None:
        """Update the indicators based on detected context."""
        cfg = self.app.config
        
        # Global
        if cfg.global_config_exists():
            self.gbl.update("● GLOBAL")
            self.gbl.set_classes("context-indicator status-on")
        else:
            self.gbl.update("○ GLOBAL")
            self.gbl.set_classes("context-indicator status-off")

        # Local
        if cfg.local_config_exists():
            self.loc.update("● LOCAL")
            self.loc.set_classes("context-indicator status-on")
        else:
            self.loc.update("○ LOCAL")
            self.loc.set_classes("context-indicator status-off")

        # Foundry
        if ContextDetector.has_foundry():
            self.fdy.update("● FOUNDRY")
            self.fdy.set_classes("context-indicator status-on")
        else:
            self.fdy.update("○ FOUNDRY")
            self.fdy.set_classes("context-indicator status-off")

        # Hardhat
        if ContextDetector.has_hardhat():
            self.hdh.update("● HARDHAT")
            self.hdh.set_classes("context-indicator status-on")
        else:
            self.hdh.update("○ HARDHAT")
            self.hdh.set_classes("context-indicator status-off")
