from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, TextArea


class AddRPCModal(ModalScreen[dict]):
    """Modal to add or edit a custom RPC."""

    def __init__(self, chain_name: str, chain_id: int, initial_data: dict | None = None):
        super().__init__()
        self.chain_name = chain_name
        self.chain_id = chain_id
        self.initial_data = initial_data or {}
        self.is_edit = bool(initial_data)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    DEFAULT_CSS = """
    AddRPCModal {
        align: center middle;
    }

    #add-rpc-container {
        width: 60;
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
        color: #6c7086;
    }

    Input {
        margin-bottom: 1;
        background: #181825;
        border: solid #313244;
    }

    Input:focus, TextArea:focus {
        border: solid #89b4fa;
    }

    TextArea {
        height: 3;
        background: #181825;
        border: solid #313244;
    }

    Checkbox {
        margin: 1 0;
    }

    .modal-buttons {
        width: 100%;
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }

    .hidden {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-rpc-container"):
            title = "Edit RPC" if self.is_edit else "Add Custom RPC"
            yield Label(f"{title} - {self.chain_name} ({self.chain_id})", classes="modal-title")

            yield Label("RPC URL", classes="field-label")
            yield Input(
                value=self.initial_data.get("url", ""),
                placeholder="https://...",
                id="url-input",
            )

            yield Checkbox(
                "Encrypt RPC URL with password?",
                value=self.initial_data.get("encrypted", False),
                id="encrypt-check",
            )

            with Vertical(id="password-section", classes="hidden"):
                yield Label("Password (required for encryption)", classes="field-label")
                yield Input(placeholder="Password", password=True, id="password-input")

            yield Label("Note @ config", classes="field-label")
            yield TextArea(self.initial_data.get("note", ""), id="note-input")

            yield Label("Secret Note @ keyring", classes="field-label")
            yield TextArea(self.initial_data.get("secret_note", ""), id="secret-note-input")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel [ESC]", id="cancel", variant="error")
                btn_text = "Save Changes" if self.is_edit else "Add RPC"
                yield Button(f"{btn_text} [Ctrl+S]", id="save", variant="success")

    def on_mount(self) -> None:
        if self.initial_data.get("encrypted"):
            self.query_one("#password-section").remove_class("hidden")

    @on(Checkbox.Changed, "#encrypt-check")
    def toggle_password(self, event: Checkbox.Changed) -> None:
        section = self.query_one("#password-section")
        if event.value:
            section.remove_class("hidden")
        else:
            section.add_class("hidden")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.action_cancel()

    def action_save(self) -> None:
        url = self.query_one("#url-input", Input).value
        if not url:
            self.app.notify("URL is required", severity="error")
            return

        data = {
            "url": url,
            "note": self.query_one("#note-input", TextArea).text,
            "secret_note": self.query_one("#secret-note-input", TextArea).text,
            "encrypt": self.query_one("#encrypt-check", Checkbox).value,
            "password": self.query_one("#password-input", Input).value,
        }
        self.dismiss(data)

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()
