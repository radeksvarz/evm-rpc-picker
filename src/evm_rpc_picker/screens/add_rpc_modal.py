import httpx
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, TextArea


class AddRPCModal(ModalScreen[dict]):
    """Modal to add or edit a custom RPC."""

    def __init__(
        self,
        chain_name: str | None = None,
        chain_id: int | None = None,
        initial_data: dict | None = None,
    ):
        super().__init__()
        self.chain_name = chain_name
        self.chain_id = chain_id
        self.initial_data = initial_data or {}
        self.is_edit = bool(initial_data)
        self.needs_chain_id = chain_id is None

    NETWORK_TYPES = [
        ("Production", "Production"),
        ("Public Testnet", "Public Testnet"),
        ("Private Testnet", "Private Testnet"),
    ]

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+g", "save_global", "Add Globally"),
        ("ctrl+l", "save_local", "Add Locally"),
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

    #chain-id-container {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }

    #chain-id-container Input {
        width: 1fr;
        margin-bottom: 0;
    }

    #detect-chain-id {
        margin: 0 0 0 1;
        min-width: 12;
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
            if self.chain_name and self.chain_id is not None:
                yield Label(f"{title} - {self.chain_name} ({self.chain_id})", classes="modal-title")
            else:
                yield Label(title, classes="modal-title")

            yield Label("RPC URL", classes="field-label")
            yield Input(
                value=self.initial_data.get("url", ""),
                placeholder="https://...",
                id="url-input",
            )

            if self.needs_chain_id:
                yield Label("Chain ID", classes="field-label")
                with Horizontal(id="chain-id-container"):
                    yield Input(
                        value=str(self.initial_data.get("chain_id", "31337")),
                        placeholder="e.g. 1, 31337",
                        id="chain-id-input",
                    )
                    yield Button("Detect", id="detect-chain-id", variant="primary")

            yield Label("Network Type", classes="field-label")
            yield Select(
                self.NETWORK_TYPES,
                value=self.initial_data.get("network_type", "Production"),
                id="network-type-select",
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
                yield Button("Cancel [Esc]", id="cancel", variant="error")
                if self.is_edit:
                    yield Button("Save Changes [^S]", id="save", variant="success")
                else:
                    yield Button("Add Globally [^G]", id="save-global", variant="primary")
                    yield Button("Add Locally [^L]", id="save-local", variant="success")

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

    @on(Button.Pressed, "#detect-chain-id")
    async def detect_chain_id(self) -> None:
        url = self.query_one("#url-input", Input).value
        if not url:
            self.app.notify("Please enter an RPC URL first", severity="error")
            return

        if "${API_KEY}" in url:
            self.app.notify("Cannot detect chain ID if URL contains ${API_KEY}", severity="warning")
            return

        btn = self.query_one("#detect-chain-id", Button)
        btn.disabled = True
        btn.label = "Detecting..."

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_chainId",
                    "params": [],
                    "id": 1,
                }
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "result" in data:
                    chain_id = int(data["result"], 16)
                    self.query_one("#chain-id-input", Input).value = str(chain_id)
                    self.app.notify(f"Detected Chain ID: {chain_id}", title="Success")
                else:
                    self.app.notify("Invalid response from RPC", severity="error")
        except Exception as e:
            self.app.notify(f"Failed to detect Chain ID: {e}", severity="error")
        finally:
            btn.disabled = False
            btn.label = "Detect"

    def _gather_data(self) -> dict | None:
        url = self.query_one("#url-input", Input).value
        if not url:
            self.app.notify("URL is required", severity="error")
            return None

        if self.needs_chain_id:
            chain_id_str = self.query_one("#chain-id-input", Input).value
            if not chain_id_str.isdigit():
                self.app.notify("Valid Chain ID is required", severity="error")
                return None
            chain_id = int(chain_id_str)
        else:
            chain_id = int(self.chain_id or 0)

        return {
            "chain_id": chain_id,
            "url": url,
            "network_type": self.query_one("#network-type-select", Select).value,
            "note": self.query_one("#note-input", TextArea).text,
            "secret_note": self.query_one("#secret-note-input", TextArea).text,
            "encrypt": self.query_one("#encrypt-check", Checkbox).value,
            "password": self.query_one("#password-input", Input).value,
        }

    def action_save(self) -> None:
        if not self.is_edit:
            return
        data = self._gather_data()
        if data:
            self.dismiss(data)

    def action_save_global(self) -> None:
        if self.is_edit:
            return
        data = self._gather_data()
        if data:
            data["is_global"] = True
            self.dismiss(data)

    def action_save_local(self) -> None:
        if self.is_edit:
            return
        data = self._gather_data()
        if data:
            data["is_global"] = False
            self.dismiss(data)

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#save-global")
    def on_save_global(self) -> None:
        self.action_save_global()

    @on(Button.Pressed, "#save-local")
    def on_save_local(self) -> None:
        self.action_save_local()
