import re
import tomllib
from pathlib import Path
from typing import Any


class ContextDetector:
    """Detects blockchain development environments (Foundry, Hardhat) in the CWD."""

    @staticmethod
    def get_foundry_rpc_endpoints() -> dict[str, str]:
        """Parse foundry.toml and return rpc_endpoints if found."""
        path = Path("./foundry.toml")
        if not path.exists():
            return {}

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                endpoints = data.get("rpc_endpoints", {})
                if isinstance(endpoints, dict):
                    return {str(k): str(v) for k, v in endpoints.items()}
                return {}
        except Exception:
            return {}

    @staticmethod
    def get_context_chain_names() -> set[str]:
        """Get names of chains mentioned in local tool configs."""
        names = set(ContextDetector.get_foundry_rpc_endpoints().keys())
        names.update(ContextDetector.get_hardhat_networks())
        return names

    @staticmethod
    def get_hardhat_networks() -> set[str]:
        """Heuristic detection of network names in hardhat config."""
        networks: set[str] = set()
        for ext in ["js", "ts"]:
            path = Path(f"./hardhat.config.{ext}")
            if path.exists():
                try:
                    content = path.read_text()
                    # Look for networks: { ... } pattern and extract keys
                    # Very simple heuristic: find keys followed by colon inside networks block
                    # We expect the networks block to end with a brace on a new line
                    match = re.search(r"networks\s*:\s*\{([\s\S]*?)\n\s*\}", content)
                    if not match:
                        # Fallback
                        match = re.search(r"networks\s*:\s*\{([\s\S]*?)\}", content)
                    if match:
                        block = match.group(1)
                        # Extract keys like 'sepolia:' or '"mainnet":'
                        keys = re.findall(r"(\w+)\s*:", block)
                        # Filter out common hardhat keywords
                        keywords = {
                            "url",
                            "accounts",
                            "chainId",
                            "gas",
                            "gasPrice",
                            "from",
                            "timeout",
                        }
                        networks.update(k for k in keys if k not in keywords)
                except Exception:
                    pass
        return networks

    @staticmethod
    def get_context_data() -> dict[str, Any]:
        """Returns combined data from all detected tool configs."""
        return {
            "foundry": ContextDetector.get_foundry_rpc_endpoints(),
            "hardhat_networks": list(ContextDetector.get_hardhat_networks()),
        }
