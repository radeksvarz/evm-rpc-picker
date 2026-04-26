from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class PasswordModal(ModalScreen[str]):
    """Modal to request password for encrypted RPC secrets."""

    DEFAULT_CSS = """
    PasswordModal {
        align: center middle;
    }

    #password-container {
        width: 40;
        height: auto;
        background: #1e1e2e;
        border: thick #89b4fa;
        padding: 1 2;
    }

    .modal-title {
        text-align: center;
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
        color: #89b4fa;
    }

    .field-label {
        margin-top: 1;
        color: #bac2de;
    }

    #password-input {
        margin: 1 0;
        background: #313244;
        border: solid #45475a;
    }

    #password-input:focus {
        border: solid #89b4fa;
    }

    .modal-buttons {
        width: 100%;
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="password-container"):
            yield Label("🔐 Encrypted RPC", classes="modal-title")
            yield Label("This RPC requires a password to unlock secrets.")
            yield Label("Password", classes="field-label")
            yield Input(placeholder="Enter password...", password=True, id="password-input")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel", variant="error")
                yield Button("Unlock", id="unlock", variant="success")

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#unlock")
    @on(Input.Submitted, "#password-input")
    def on_submit(self) -> None:
        password = self.query_one("#password-input", Input).value
        if password:
            self.dismiss(password)
        else:
            self.app.notify("Password is required", severity="error")
