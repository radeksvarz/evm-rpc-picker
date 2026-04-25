import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListView, Static

from ..widgets import RPCListItem


class RPCScreen(ModalScreen[str]):
    """Screen to select RPC and check latency."""

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

    #rpc-list {
        height: 1fr;
        border: solid #313244;
        background: #181825;
        margin: 1 0;
    }

    .latency-label {
        width: 12;
        text-align: right;
        color: #fab387;
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

    def __init__(self, chain: Dict[str, Any]):
        super().__init__()
        self.chain = chain
        self.rpc_urls = [r["url"] for r in chain.get("rpc", []) if r.get("url") and not r["url"].startswith("wss://")]

    def compose(self) -> ComposeResult:
        with Container(id="rpc-container"):
            yield Label(f"[bold #89b4fa]Select RPC for {self.chain.get('name', 'Unknown')}[/bold #89b4fa]")
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
        for url in self.rpc_urls:
            item = RPCListItem(url)
            items.append(item)
            rpc_list.append(item)
            
        # Run latency checks in background
        self.check_latencies(items)

    @work
    async def check_latencies(self, items: List[RPCListItem]) -> None:
        async with httpx.AsyncClient(timeout=2.5) as client:
            tasks = [self.ping_rpc(client, item) for item in items]
            await asyncio.gather(*tasks)
            
        # Sort by latency
        rpc_list = self.query_one("#rpc-list", ListView)
        sorted_items = sorted(items, key=lambda x: (x.latency is None, x.latency or 9999))
        
        rpc_list.clear()
        for item in sorted_items:
            rpc_list.append(item)
        
        # Reset selection to top after sort
        await asyncio.sleep(0.05)
        if rpc_list.children:
            rpc_list.index = 0
            rpc_list.focus()

    async def ping_rpc(self, client: httpx.AsyncClient, item: RPCListItem) -> None:
        start = time.time()
        try:
            # Simple JSON-RPC call to check latency
            payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
            response = await client.post(item.url, json=payload)
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
            self.run_worker(self.refresh_rpcs())
        elif event.button.id == "btn-select":
            self.action_submit()

    def action_submit(self) -> None:
        rpc_list = self.query_one("#rpc-list", ListView)
        if rpc_list.highlighted_child:
            self.dismiss(rpc_list.highlighted_child.url)

    def on_key(self, event: Any) -> None:
        if event.key == "escape" or event.key == "b":
            self.dismiss(None)
        elif event.key == "r":
            self.run_worker(self.refresh_rpcs())
        elif event.key == "enter" or event.key == "s":
            self.action_submit()
