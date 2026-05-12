import json
import os
import pathlib
import typing
from unittest.mock import patch

import pytest
from textual.widgets import DataTable

from evm_rpc_picker.screens.main_screen import MainScreen
from evm_rpc_picker.screens.rpc_screen import RPCScreen
from evm_rpc_picker.tui import ChainRPCPicker
from evm_rpc_picker.widgets.chains_table import ChainsTable

# Mock data
MOCK_CHAINS = [
    {
        "name": "Ethereum Mainnet",
        "chainId": 1,
        "shortName": "eth",
        "nativeCurrency": {"symbol": "ETH"},
        "rpc": ["https://eth-mainnet.public.blastapi.io", "https://rpc.ankr.com/eth"],
        "isTestnet": False,
    },
    {
        "name": "Sepolia",
        "chainId": 11155111,
        "shortName": "sep",
        "nativeCurrency": {"symbol": "ETH"},
        "rpc": ["https://rpc.sepolia.org"],
        "isTestnet": True,
    },
]


@pytest.fixture(autouse=True)
def mock_cache_file(tmp_path: pathlib.Path) -> typing.Generator[None, None, None]:
    # This fixture will run for every test and set a separate cache file
    cache_path = tmp_path / "test_chains.json"
    os.environ["EVM_RPC_PICKER_CACHE_FILE"] = str(cache_path)

    # Pre-populate cache to avoid network calls
    with open(cache_path, "w") as f:
        json.dump(MOCK_CHAINS, f)

    global_dir = tmp_path / "global"
    global_dir.mkdir()
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_file = local_dir / ".rpc-picker.toml"

    # Create an empty local config to avoid ConfirmModal
    local_file.write_text("[favorites]\n")

    with (
        patch("evm_rpc_picker.config.user_config_dir", return_value=str(global_dir)),
        patch("evm_rpc_picker.config.ConfigManager.LOCAL_CONFIG_FILE", local_file),
        patch(
            "evm_rpc_picker.config.ConfigManager.GLOBAL_CONFIG_FILE",
            global_dir / "config.toml",
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_navigation_to_rpc_screen() -> None:
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RPCScreen)


@pytest.mark.asyncio
async def test_rpc_screen_back_navigation() -> None:
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RPCScreen)

        await pilot.press("escape")
        await pilot.pause(0.2)
        assert isinstance(app.screen, MainScreen)


@pytest.mark.asyncio
async def test_rpc_selection_and_exit() -> None:
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause(0.5)

        data_table = app.screen.query_one(DataTable)
        if data_table.row_count > 0:
            data_table.move_cursor(row=0)

        data_table.focus()

        with patch.object(app, "exit") as mock_exit:
            await app.screen.run_action("submit")
            await pilot.pause(0.2)
            mock_exit.assert_called()
