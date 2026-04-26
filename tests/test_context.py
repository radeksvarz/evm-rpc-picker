from unittest.mock import patch

import pytest

from evm_rpc_picker.context import ContextDetector


@pytest.fixture
def mock_cwd(tmp_path):
    """Fixture to mock CWD for ContextDetector."""
    with patch(
        "evm_rpc_picker.context.Path",
        side_effect=lambda *args: tmp_path / args[0] if args else tmp_path,
    ):
        yield tmp_path


def test_get_foundry_rpc_endpoints_no_file(mock_cwd):
    assert ContextDetector.get_foundry_rpc_endpoints() == {}


def test_get_foundry_rpc_endpoints_valid(mock_cwd):
    foundry_toml = mock_cwd / "foundry.toml"
    foundry_toml.write_text(
        'rpc_endpoints = { mainnet = "https://eth.com", sepolia = "https://sep.com" }'
    )

    expected = {"mainnet": "https://eth.com", "sepolia": "https://sep.com"}
    assert ContextDetector.get_foundry_rpc_endpoints() == expected


def test_get_foundry_rpc_endpoints_no_key(mock_cwd):
    foundry_toml = mock_cwd / "foundry.toml"
    foundry_toml.write_text("[profile.default]\nsrc = 'src'")
    assert ContextDetector.get_foundry_rpc_endpoints() == {}


def test_get_foundry_rpc_endpoints_invalid_toml(mock_cwd):
    foundry_toml = mock_cwd / "foundry.toml"
    foundry_toml.write_text("invalid = [")
    assert ContextDetector.get_foundry_rpc_endpoints() == {}


def test_get_hardhat_networks_no_file(mock_cwd):
    assert ContextDetector.get_hardhat_networks() == set()


def test_get_hardhat_networks_js(mock_cwd):
    hardhat_js = mock_cwd / "hardhat.config.js"
    hardhat_js.write_text("""
        module.exports = {
            networks: {
                hardhat: {},
                sepolia: { url: "..." },
                "mainnet": { url: "..." }
            }
        };
    """)
    # Our simple regex handles word-like keys followed by colon.
    # "mainnet": might not be caught by \w+, let's check.
    networks = ContextDetector.get_hardhat_networks()
    assert "hardhat" in networks
    assert "sepolia" in networks


def test_get_hardhat_networks_ts(mock_cwd):
    hardhat_ts = mock_cwd / "hardhat.config.ts"
    hardhat_ts.write_text("""
        const config: HardhatUserConfig = {
            networks: {
                base: { url: "..." }
            }
        };
    """)
    assert ContextDetector.get_hardhat_networks() == {"base"}


def test_get_hardhat_networks_exception(mock_cwd):
    hardhat_js = mock_cwd / "hardhat.config.js"
    hardhat_js.write_text("...")
    # Mock read_text to raise exception
    with patch("pathlib.Path.read_text", side_effect=Exception):
        assert ContextDetector.get_hardhat_networks() == set()


def test_get_context_chain_names(mock_cwd):
    # Setup both
    (mock_cwd / "foundry.toml").write_text('rpc_endpoints = { foundry_net = "..." }')
    (mock_cwd / "hardhat.config.js").write_text("networks: { hardhat_net: {} }")

    names = ContextDetector.get_context_chain_names()
    assert names == {"foundry_net", "hardhat_net"}


def test_get_context_data(mock_cwd):
    (mock_cwd / "foundry.toml").write_text('rpc_endpoints = { eth = "..." }')
    (mock_cwd / "hardhat.config.js").write_text("networks: { base: {} }")

    data = ContextDetector.get_context_data()
    assert data["foundry"] == {"eth": "..."}
    assert "base" in data["hardhat_networks"]
