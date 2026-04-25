import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from platformdirs import user_cache_dir

CACHE_DIR = Path(user_cache_dir("evm-rpc-picker"))
CACHE_FILE = CACHE_DIR / "chains.json"
CHAINS_URL = "https://chainlist.org/rpcs.json"

def get_cached_chains() -> Optional[List[Dict[str, Any]]]:
    """Return cached chains if valid (less than 24h old)."""
    if CACHE_FILE.exists():
        mtime = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=24):
            try:
                with open(CACHE_FILE, "r") as f:
                    return sorted(json.load(f), key=lambda x: x.get("chainId", 0))
            except Exception:
                pass
    return None

async def fetch_chains() -> List[Dict[str, Any]]:
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
                if any(p in url.lower() for p in ["infura.io", "alchemy.com", "api_key", "api-key"]):
                    continue
                filtered_rpc.append(r)
            
            if filtered_rpc:
                c["rpc"] = filtered_rpc
                chains.append(c)
                
        chains.sort(key=lambda x: x.get("chainId", 0))
        
        with open(CACHE_FILE, "w") as f:
            json.dump(chains, f)
        return chains

def clear_cache():
    """Remove the local cache file."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
