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

    @staticmethod
    def has_foundry() -> bool:
        """Check if foundry.toml exists."""
        return Path("./foundry.toml").exists()

    @staticmethod
    def has_hardhat() -> bool:
        """Check if hardhat config exists."""
        return any(Path(f"./hardhat.config.{ext}").exists() for ext in ["js", "ts"])

    @staticmethod
    def _check_strong_url(t_name: str, t_url: str, name: str, short: str) -> int | None:
        """Helper to check for strong Alchemy/Infura URL matches."""

        def hw(w: str, t: str) -> bool:
            return re.search(rf"\b{w}\b", t.lower()) is not None

        if "alchemy" not in t_url and "infura" not in t_url:
            return None

        if t_name in t_url:
            is_eth = "eth-" in t_url or "ethereum" in t_url
            is_e_c = hw("ethereum", name) or hw("eth", name) or short == "eth"
            is_s_c = hw("sepolia", name) or t_name == "sepolia"

            if is_eth and is_e_c and is_s_c:
                return 1
            if ("arb-" in t_url or "arbitrum" in t_url) and hw("arbitrum", name):
                return 1
            if ("base-" in t_url or "base" in t_url) and hw("base", name):
                return 1
        return None

    @staticmethod
    def _get_chain_priority(
        t_name: str, t_url: str, name: str, short: str, aliases: dict, generic: set
    ) -> int | None:
        """Determines matching priority for a single chain."""

        def has_word(w: str, text: str) -> bool:
            return re.search(rf"\b{w}\b", text.lower()) is not None

        # Priority 0: Exact
        if t_name == name or t_name == short:
            return 0

        # Priority 1: Strong URL Match
        prio1 = ContextDetector._check_strong_url(t_name, t_url, name, short)
        if prio1 is not None:
            return prio1

        # Priority 2: Alias
        if t_name in aliases:
            if any(a == name or a == short for a in aliases[t_name]):
                return 2

        # Priority 3: Weak URL Match
        if "alchemy" in t_url or "infura" in t_url:
            is_t = f"-{t_name}" in t_url or f"{t_name}-" in t_url
            if is_t and (t_name in name or t_name in short):
                return 3

        # Priority 4: Substring
        if t_name not in generic and len(t_name) > 3 and t_name in name:
            return 4

        return None

    @staticmethod
    def match_names_to_ids(names_to_urls: dict[str, str], chains: list[dict[str, Any]]) -> set[int]:
        """Tolerant but precise matching of names and URLs from tool configs to chain IDs."""
        aliases = {
            "mainnet": ["eth", "ethereum mainnet"],
            "arbitrum": ["arb", "arbitrum one"],
            "optimism": ["oeth", "op mainnet"],
            "polygon": ["matic", "polygon mainnet"],
            "base": ["base mainnet"],
            "sepolia": ["sep", "sepolia testnet", "eth-sepolia", "ethereum sepolia"],
        }
        result_ids = set()
        generic = {"mainnet", "testnet", "chain"}

        for t_name, t_url in names_to_urls.items():
            t_name, t_url = t_name.lower(), t_url.lower()
            candidates = []

            for c in chains:
                name, short, cid = (
                    c.get("name", "").lower(),
                    c.get("shortName", "").lower(),
                    c["chainId"],
                )
                prio = ContextDetector._get_chain_priority(
                    t_name, t_url, name, short, aliases, generic
                )
                if prio is not None:
                    candidates.append((prio, cid))

            if candidates:
                candidates.sort()
                result_ids.add(candidates[0][1])

        return result_ids
