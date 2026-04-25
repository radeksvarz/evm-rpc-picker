import pytest
import respx
import httpx
from evm_rpc_picker.models import fetch_chains, CHAINS_URL

@pytest.mark.asyncio
@respx.mock
async def test_fetch_chains_filtering():
    # Mock data with one valid RPC and one Infura/Alchemy (which should be filtered)
    mock_data = [
        {
            "name": "Ethereum Mainnet",
            "chainId": 1,
            "rpc": [
                {"url": "https://eth.llamarpc.com", "tracking": "none"},
                {"url": "https://mainnet.infura.io/v3/API_KEY", "tracking": "infura"}
            ],
            "nativeCurrency": {"name": "Ether", "symbol": "ETH", "decimals": 18}
        },
        {
            "name": "Test Chain",
            "chainId": 999,
            "rpc": ["https://rpc.test.com"],
            "nativeCurrency": {"name": "Test", "symbol": "TEST", "decimals": 18}
        }
    ]
    
    respx.get(CHAINS_URL).mock(return_value=httpx.Response(200, json=mock_data))
    
    chains = await fetch_chains()
    
    assert len(chains) == 2
    # Check that Infura RPC was filtered out from Ethereum Mainnet
    eth = next(c for c in chains if c["chainId"] == 1)
    rpc_urls = [r["url"] if isinstance(r, dict) else r for r in eth["rpc"]]
    assert "https://eth.llamarpc.com" in rpc_urls
    assert not any("infura.io" in str(r) for r in rpc_urls)
    
    # Check that string-based RPC list is preserved
    test_chain = next(c for c in chains if c["chainId"] == 999)
    assert "https://rpc.test.com" in test_chain["rpc"]
