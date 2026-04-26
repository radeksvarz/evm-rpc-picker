import os
import json
import pytest
from unittest.mock import patch, MagicMock
from evm_rpc_picker.tui import ChainRPCPicker
from evm_rpc_picker.widgets.search_input import SearchInput
from evm_rpc_picker.widgets.chains_table import ChainsTable
from evm_rpc_picker.widgets.env_status import EnvStatus
from evm_rpc_picker.screens.main_screen import MainScreen
from evm_rpc_picker.screens.rpc_screen import RPCScreen

# Mock data
MOCK_CHAINS = [
    {
        "name": "Ethereum Mainnet",
        "chainId": 1,
        "shortName": "eth",
        "nativeCurrency": {"symbol": "ETH"},
        "rpc": ["https://eth-mainnet.public.blastapi.io", "https://rpc.ankr.com/eth"],
        "isTestnet": False
    },
    {
        "name": "Sepolia",
        "chainId": 11155111,
        "shortName": "sep",
        "nativeCurrency": {"symbol": "ETH"},
        "rpc": ["https://rpc.sepolia.org"],
        "isTestnet": True
    }
]

@pytest.fixture(autouse=True)
def mock_cache_file(tmp_path):
    # This fixture will run for every test and set a separate cache file
    cache_path = tmp_path / "test_chains.json"
    os.environ["EVM_RPC_PICKER_CACHE_FILE"] = str(cache_path)
    
    # Pre-populate cache to avoid network calls
    with open(cache_path, "w") as f:
        json.dump(MOCK_CHAINS, f)
        
    yield
    if "EVM_RPC_PICKER_CACHE_FILE" in os.environ:
        del os.environ["EVM_RPC_PICKER_CACHE_FILE"]

@pytest.mark.asyncio
async def test_app_focus_cycling():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        # Check initial focus
        assert isinstance(app.focused, SearchInput)
        
        # Press Tab to move to table
        await pilot.press("tab")
        assert isinstance(app.focused, ChainsTable)
        
        # Press Tab to move to env status
        await pilot.press("tab")
        assert app.focused.id == "env-status-widget"
        
        # Press Tab to wrap back to SearchInput
        await pilot.press("tab")
        assert isinstance(app.focused, SearchInput)

@pytest.mark.asyncio
async def test_search_filtering():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        # Wait for data to load from cache
        await pilot.pause()
        
        # Search for Sepolia
        await pilot.press(*"sepolia")
        await pilot.pause()
        
        main_screen = app.screen
        assert len(main_screen.filtered_chains) == 1
        assert main_screen.filtered_chains[0]["name"] == "Sepolia"

@pytest.mark.asyncio
async def test_filter_toggle():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause()
        main_screen = app.screen
        
        # Initial: ALL (2 chains)
        assert main_screen.filter_mode == "all"
        assert len(main_screen.filtered_chains) == 2
        
        # Press Ctrl+T -> MAINNET (1 chain)
        await pilot.press("ctrl+t")
        assert main_screen.filter_mode == "mainnet"
        assert len(main_screen.filtered_chains) == 1
        assert main_screen.filtered_chains[0]["chainId"] == 1
        
        # Press Ctrl+T -> TESTNET (1 chain)
        await pilot.press("ctrl+t")
        assert main_screen.filter_mode == "testnet"
        assert len(main_screen.filtered_chains) == 1
        assert main_screen.filtered_chains[0]["chainId"] == 11155111
        
        # Press Ctrl+T -> ALL again
        await pilot.press("ctrl+t")
        assert main_screen.filter_mode == "all"
        assert len(main_screen.filtered_chains) == 2

@pytest.mark.asyncio
async def test_navigation_to_rpc_screen():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause()
        
        # Move focus to table and press Right
        await pilot.press("tab")
        await pilot.press("right")
        
        # Should now be on RPCScreen
        assert isinstance(app.screen, RPCScreen)
        assert app.screen.chain["name"] == "Ethereum Mainnet"

@pytest.mark.asyncio
async def test_rpc_screen_back_navigation():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.pause()
        
        # Enter RPCScreen
        await pilot.press("tab", "right")
        assert isinstance(app.screen, RPCScreen)
        
        # Press Left to go back
        await pilot.press("left")
        assert isinstance(app.screen, MainScreen)

@pytest.mark.asyncio
async def test_rpc_selection_and_exit():
    app = ChainRPCPicker()
    # Mock ping_rpc instead of check_latencies to let the sorting/selection logic run
    with patch("evm_rpc_picker.screens.rpc_screen.RPCScreen.ping_rpc", return_value=None):
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Select first chain (Ethereum)
            await pilot.press("tab", "right")
            # Wait for RPCScreen to mount and run workers
            await pilot.pause()
            # Give it a bit more time for the latency check worker to finish (it's mocked but still async)
            import asyncio
            await asyncio.sleep(0.2)
            
            # Ensure the list has an index
            from textual.widgets import ListView
            rpc_list = app.screen.query_one(ListView)
            if rpc_list.index is None and rpc_list.children:
                rpc_list.index = 0
            
            # Press Enter to select
            await pilot.press("enter")
            await pilot.pause()
            
            # The app should have exited with one of the URLs
            # Since we didn't actually ping, sorting might be stable or random-ish but items are there
            assert app.return_value in ["https://eth-mainnet.public.blastapi.io", "https://rpc.ankr.com/eth"]

@pytest.mark.asyncio
async def test_env_status_widget_latency():
    # Mock ETH_RPC_URL and the network response
    with patch.dict(os.environ, {"ETH_RPC_URL": "https://mock-rpc.com"}):
        with patch("httpx.AsyncClient.post") as mock_post:
            # Mock a successful RPC response
            mock_post.return_value = MagicMock(status_code=200)
            
            app = ChainRPCPicker()
            async with app.run_test() as pilot:
                await pilot.pause()
                # Give the worker a moment to finish
                import asyncio
                await asyncio.sleep(0.1)
                
                env_status = app.screen.query_one(EnvStatus)
                # Access .content for assertion (confirmed via debug)
                latency_text = str(env_status.latency_label.content)
                status_text = str(env_status.status_label.content)
                assert "ms" in latency_text
                assert "https://mock-rpc.com" in status_text

@pytest.mark.asyncio
async def test_env_status_widget_enter_select():
    # Mock ETH_RPC_URL
    rpc_url = "https://current-rpc.com"
    with patch.dict(os.environ, {"ETH_RPC_URL": rpc_url}):
        app = ChainRPCPicker()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Tab to the widget
            await pilot.press("tab", "tab")
            assert app.focused.id == "env-status-widget"
            
            # Press Enter
            await pilot.press("enter")
            await pilot.pause()
            
            # App should return the URL
            assert app.return_value == rpc_url

@pytest.mark.asyncio
async def test_quit_on_esc():
    app = ChainRPCPicker()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        assert not app.is_running
