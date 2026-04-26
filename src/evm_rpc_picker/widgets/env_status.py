import os
import time
import asyncio
import httpx
from typing import Optional
from textual import work
from textual.containers import Horizontal
from textual.widgets import Label

class EnvStatus(Horizontal):
    DEFAULT_CSS = """
    EnvStatus {
        background: #181825;
        height: 3;
        width: 100%;
        padding: 0 2;
        border-top: solid #313244;
        content-align: left middle;
    }

    #env-status-label {
        color: #9399b2;
        width: 1fr;
        height: 1;
        text-style: italic;
    }

    #env-latency-label {
        width: 10;
        text-align: right;
    }

    EnvStatus:focus #env-status-label {
        background: #313244;
        color: #f5c2e7;
        text-style: bold italic;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.current_rpc: Optional[str] = os.environ.get("ETH_RPC_URL")
        self.status_label = Label(id="env-status-label")
        self.latency_label = Label("--- ms", id="env-latency-label")

    def compose(self):
        yield self.status_label
        yield self.latency_label

    def on_mount(self):
        self.update_status()
        if self.current_rpc:
            self.check_latency()

    def update_status(self):
        display_rpc = self.current_rpc or "not set"
        self.status_label.update(f" Current ETH_RPC_URL: [bold #89b4fa]{display_rpc}[/bold #89b4fa]")

    @work(exclusive=True)
    async def check_latency(self):
        if not self.current_rpc:
            return

        async with httpx.AsyncClient(timeout=2.5) as client:
            start = time.time()
            try:
                response = await client.post(
                    self.current_rpc,
                    json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
                )
                if response.status_code == 200:
                    latency = (time.time() - start) * 1000
                    color = "#00ff00" if latency < 200 else "#ffff00" if latency < 500 else "#ff0000"
                    self.latency_label.update(f"[{color}]{latency:.0f} ms[/{color}]")
                else:
                    self.latency_label.update("[red]ERR[/red]")
            except Exception:
                self.latency_label.update("[red]ERR[/red]")
