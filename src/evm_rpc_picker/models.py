import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from platformdirs import user_cache_dir

CACHE_DIR = Path(user_cache_dir("evm-rpc-picker"))
DEFAULT_CACHE_FILE = CACHE_DIR / "chains.json"
CHAINS_URL = "https://chainlist.org/rpcs.json"


def get_cache_file() -> Path:
    import os

    env_path = os.environ.get("EVM_RPC_PICKER_CACHE_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_CACHE_FILE


def get_cached_chains() -> list[dict[str, Any]] | None:
    """Return cached chains if valid (less than 24h old)."""
    cache_file = get_cache_file()
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=24):
            try:
                with open(cache_file) as f:
                    return sorted(json.load(f), key=lambda x: x.get("chainId", 0))
            except Exception:
                pass
    return None


async def fetch_chains() -> list[dict[str, Any]]:
    """Fetch chains from chainlist.org and cache them."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        response = await client.get(CHAINS_URL)
        response.raise_for_status()
        data = response.json()

        # Filter and process chains
        chains = []
        for c in data:
            if not c.get("rpc"):
                continue

            # Filter out RPCs that require API keys (Infura, Alchemy, etc.)
            filtered_rpc = []
            for r in c.get("rpc", []):
                url = r["url"] if isinstance(r, dict) else r
                if not url:
                    continue
                # Exclude common providers that usually require keys in public lists
                if any(
                    p in url.lower() for p in ["infura.io", "alchemy.com", "api_key", "api-key"]
                ):
                    continue
                filtered_rpc.append(r)

            if filtered_rpc:
                c["rpc"] = filtered_rpc
                chains.append(c)

        chains.sort(key=lambda x: x.get("chainId", 0))

        cache_file = get_cache_file()
        with open(cache_file, "w") as f:
            json.dump(chains, f)
        return chains


def clear_cache() -> None:
    """Remove the local cache file."""
    cache_file = get_cache_file()
    if cache_file.exists():
        cache_file.unlink()
