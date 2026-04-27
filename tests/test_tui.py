import json
import os
from unittest.mock import patch

import pytest

from evm_rpc_picker.screens.main_screen import MainScreen
from evm_rpc_picker.screens.rpc_screen import RPCScreen
from evm_rpc_picker.tui import ChainRPCPicker
from evm_rpc_picker.widgets.chains_table import ChainsTable
from evm_rpc_picker.widgets.env_status import EnvStatus
from evm_rpc_picker.widgets.search_input import SearchInput

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
def mock_cache_file(tmp_path):
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
async def test_app_initial_load():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        # Check current screen
        assert isinstance(app.screen, MainScreen)
        table = app.screen.query_one(ChainsTable)
        # Should have 2 mock chains
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_search_filtering():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        # Type "Sep"
        for char in "sepolia":
            await pilot.press(char)
        await pilot.pause(0.2)

        table = app.screen.query_one(ChainsTable)
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_filter_toggle():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        main_screen = app.screen
        table = main_screen.query_one(ChainsTable)

        assert main_screen.filter_type == "all"
        await pilot.press("ctrl+t")
        await pilot.pause(0.2)
        assert main_screen.filter_type == "testnet"
        assert table.row_count == 1

        await pilot.press("ctrl+t")
        await pilot.pause(0.2)
        assert main_screen.filter_type == "mainnet"
        assert table.row_count == 1

        await pilot.press("ctrl+t")
        await pilot.pause(0.2)
        assert main_screen.filter_type == "all"
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_navigation_to_rpc_screen():
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
async def test_rpc_screen_back_navigation():
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
async def test_rpc_selection_and_exit():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause(0.5)

        from textual.widgets import ListView

        list_view = app.screen.query_one(ListView)
        if list_view.index is None and len(list_view) > 0:
            list_view.index = 0

        list_view.focus()

        with patch.object(app, "exit") as mock_exit:
            await app.screen.run_action("submit")
            await pilot.pause(0.2)
            mock_exit.assert_called()


@pytest.mark.asyncio
async def test_env_status_widget_latency():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        env_status = app.screen.query_one(EnvStatus)
        await pilot.pause(0.5)
        assert env_status is not None


@pytest.mark.asyncio
async def test_env_status_widget_enter_select():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        env_status = app.screen.query_one(EnvStatus)
        env_status.focus()
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert app.focused is not None


@pytest.mark.asyncio
async def test_type_to_search_from_table():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()

        await pilot.press("s")
        await pilot.press("e")
        await pilot.press("p")
        await pilot.pause(0.2)

        search_input = app.screen.query_one("#search-input", SearchInput)
        assert search_input.value == "sep"


@pytest.mark.asyncio
async def test_favorite_toggle():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        main_screen = app.screen
        table = main_screen.query_one(ChainsTable)
        table.focus()
        table.move_cursor(row=0)

        with patch.object(app.config, "toggle_favorite") as mock_toggle:
            await main_screen.run_action("toggle_favorite")
            await pilot.pause(0.2)
            mock_toggle.assert_called()


@pytest.mark.asyncio
async def test_slash_is_typed_into_search():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        table = app.screen.query_one(ChainsTable)
        table.focus()

        await pilot.press("slash")
        await pilot.pause(0.2)

        search_input = app.screen.query_one("#search-input")
        assert search_input.value == "/"
        assert app.focused == table


@pytest.mark.asyncio
async def test_esc_clears_search_then_quits():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        search_input = app.screen.query_one("#search-input")
        
        # 1. Type something
        await pilot.press("a")
        assert search_input.value == "a"
        
        # 2. First ESC clears search
        await pilot.press("escape")
        assert search_input.value == ""
        
        # 3. Second ESC quits
        with patch.object(app, "exit") as mock_exit:
            await pilot.press("escape")
            await pilot.pause(0.2)
            mock_exit.assert_called_once()
@pytest.mark.asyncio
async def test_backspace_clears_search():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        search_input = app.screen.query_one("#search-input")
        
        await pilot.press("a")
        await pilot.press("b")
        assert search_input.value == "ab"
        
        await pilot.press("backspace")
        assert search_input.value == "a"
        
        await pilot.press("backspace")
        assert search_input.value == ""
