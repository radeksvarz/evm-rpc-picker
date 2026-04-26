from unittest.mock import patch

from evm_rpc_picker import pick_rpc


def test_pick_rpc_as_module():
    """
    Example showing how to use evm_rpc_picker as a module.
    We mock the app.run() to avoid opening the actual TUI in tests.
    """
    mock_url = "https://eth-mainnet.public.blastapi.io"

    with patch("evm_rpc_picker.ChainRPCPicker.run", return_value=mock_url):
        # This is how you call it in your code:
        rpc_url = pick_rpc()

        assert rpc_url == mock_url
        assert isinstance(rpc_url, str)


def test_pick_rpc_cancel():
    """Example showing handling of user cancellation."""
    with patch("evm_rpc_picker.ChainRPCPicker.run", return_value=None):
        rpc_url = pick_rpc()
        # app.run() returns None on ESC, pick_rpc() returns that
        assert rpc_url is None
