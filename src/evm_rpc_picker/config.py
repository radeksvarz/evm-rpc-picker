import json
import time
from pathlib import Path
from typing import Any, cast

import keyring
import tomlkit
from platformdirs import user_config_dir

from .encryption import EncryptionManager


class ConfigManager:
    """Manages global and local configurations for the EVM RPC Picker."""

    APP_NAME = "evm-rpc-picker"
    GLOBAL_CONFIG_DIR = Path(user_config_dir(APP_NAME))
    GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.toml"
    LOCAL_CONFIG_FILE = Path("./.rpc-picker.toml")

    def __init__(self) -> None:
        self.global_config: dict[str, Any] = self._load_toml(self.GLOBAL_CONFIG_FILE)
        self.local_config: dict[str, Any] = self._load_toml(self.LOCAL_CONFIG_FILE)
        self.encryption_manager = EncryptionManager()

    def _load_toml(self, path: Path) -> dict[str, Any]:
        """Load configuration from a TOML file."""
        if path.exists():
            try:
                # Use tomlkit to preserve structure/comments for later
                return dict(tomlkit.parse(path.read_text()))
            except Exception:
                return {}
        return {}

    # --- Favorites ---

    def get_favorites(self, project_only: bool = False) -> set[int]:
        """Get a set of favorite chain IDs from both configs or just local."""
        favorites = set(self.local_config.get("favorites", []))
        if not project_only:
            favorites.update(self.global_config.get("favorites", []))
        return favorites

    def toggle_favorite(self, chain_id: int, is_global: bool = False) -> None:
        """Toggle a favorite chain ID in the specified config. Auto-creates file if missing."""
        config = self.global_config if is_global else self.local_config
        path = self.GLOBAL_CONFIG_FILE if is_global else self.LOCAL_CONFIG_FILE

        favorites = list(config.get("favorites", []))
        if chain_id in favorites:
            favorites.remove(chain_id)
        else:
            favorites.append(chain_id)

        config["favorites"] = favorites
        self._save_toml(path, config, is_global=is_global)

        # Update internal state
        if is_global:
            self.global_config = config
        else:
            self.local_config = config

    # --- Secrets ---

    def set_secret(self, key_name: str, secret_value: str) -> None:
        """Store a secret value in the system keyring."""
        keyring.set_password(self.APP_NAME, key_name, secret_value)

    def get_secret(self, key_name: str) -> str | None:
        """Retrieve a secret value from the system keyring."""
        return keyring.get_password(self.APP_NAME, key_name)

    def delete_secret(self, key_name: str) -> None:
        """Remove a secret from the system keyring."""
        try:
            keyring.delete_password(self.APP_NAME, key_name)
        except keyring.errors.PasswordDeleteError:
            pass

    def save_rpc_secret(
        self,
        key_name: str,
        api_key: str,
        secret_note: str = "",
        password: str | None = None,
    ) -> None:
        """Save API key and secret note to keyring, optionally encrypted with a password."""
        data = {
            "api_key": api_key,
            "secret_note": secret_note,
            "encrypted": password is not None,
        }

        if password:
            json_str = json.dumps(data)
            blob, salt = EncryptionManager.encrypt(json_str, password)
            storage_data = {"blob": blob, "salt": salt, "encrypted": True}
            self.set_secret(key_name, json.dumps(storage_data))
        else:
            self.set_secret(key_name, json.dumps(data))

    def load_rpc_secret(self, key_name: str, password: str | None = None) -> dict[str, Any]:
        """Load and optionally decrypt RPC secret from keyring."""
        raw_val = self.get_secret(key_name)
        if not raw_val:
            return {}

        try:
            data = json.loads(raw_val)
            if data.get("encrypted"):
                if not password:
                    return {"status": "needs_password", "encrypted": True}

                decrypted_json = EncryptionManager.decrypt(data["blob"], data["salt"], password)
                if not decrypted_json:
                    return {"status": "wrong_password", "encrypted": True}

                result = cast(dict[str, Any], json.loads(decrypted_json))
                result["status"] = "ok"
                return result

            data["status"] = "ok"
            return cast(dict[str, Any], data)
        except Exception:
            return {"status": "error"}

    # --- Custom RPCs ---

    @staticmethod
    def smart_extract_key(url: str) -> tuple[str, str]:
        """Extract API key from known RPC providers."""
        if "/v3/" in url:
            parts = url.split("/v3/")
            return parts[0] + "/v3/${API_KEY}", parts[1]
        if "/v2/" in url:
            parts = url.split("/v2/")
            return parts[0] + "/v2/${API_KEY}", parts[1]
        return url, ""

    def get_custom_rpcs(self, chain_id: int) -> list[dict[str, Any]]:
        """Get custom RPCs for a chain from both configs."""
        # Merge global and local custom RPCs
        global_rpcs = self.global_config.get("custom_rpcs", {}).get(str(chain_id), [])
        local_rpcs = self.local_config.get("custom_rpcs", {}).get(str(chain_id), [])

        # Tag them for UI differentiation
        for rpc in global_rpcs:
            rpc["source"] = "global"
        for rpc in local_rpcs:
            rpc["source"] = "project"

        return cast(list[dict[str, Any]], local_rpcs + global_rpcs)

    def add_custom_rpc(
        self,
        chain_id: int,
        rpc_data: dict[str, Any],
        is_global: bool = False,
        password: str | None = None,
    ) -> None:
        """Add a custom RPC to the specified config, handling secrets."""
        config = self.global_config if is_global else self.local_config

        # 1. Handle Secrets
        url = rpc_data.get("url", "")
        base_url, api_key = self.smart_extract_key(url)

        secret_note = rpc_data.get("secret_note", "")
        password = rpc_data.get("password")

        # Only use keyring if there's something secret
        rpc_id = f"rpc_{chain_id}_{int(time.time())}"
        is_encrypted = False

        if api_key or secret_note:
            self.save_rpc_secret(rpc_id, api_key, secret_note, password=password)
            is_encrypted = password is not None

        # 2. Save public part
        custom_rpcs = config.get("custom_rpcs", {})
        cid_str = str(chain_id)
        if cid_str not in custom_rpcs:
            custom_rpcs[cid_str] = []

        entry = {
            "id": rpc_id,
            "url": base_url if api_key else url,
            "note": rpc_data.get("note", ""),
            "encrypted": is_encrypted,
            "has_secrets": bool(api_key or secret_note),
        }

        custom_rpcs[cid_str].append(entry)
        config["custom_rpcs"] = custom_rpcs

        if is_global:
            self._save_toml(self.GLOBAL_CONFIG_FILE, config, is_global=True)
            self.global_config = config
        else:
            self._save_toml(self.LOCAL_CONFIG_FILE, config, is_global=False)
            self.local_config = config

    def update_custom_rpc(
        self,
        chain_id: int,
        rpc_id: str,
        rpc_data: dict[str, Any],
        is_global: bool = False,
    ) -> None:
        """Update an existing custom RPC in the specified config."""
        config = self.global_config if is_global else self.local_config
        custom_rpcs = config.get("custom_rpcs", {})
        cid_str = str(chain_id)

        if cid_str not in custom_rpcs:
            return

        # Find the index of the RPC to update
        index = -1
        for i, rpc in enumerate(custom_rpcs[cid_str]):
            if rpc["id"] == rpc_id:
                index = i
                break

        if index == -1:
            return

        # 1. Handle Secrets (same as add_custom_rpc, but keep same rpc_id)
        url = rpc_data.get("url", "")
        base_url, api_key = self.smart_extract_key(url)
        secret_note = rpc_data.get("secret_note", "")
        password = rpc_data.get("password")
        is_encrypted = password is not None

        if api_key or secret_note:
            self.save_rpc_secret(rpc_id, api_key, secret_note, password=password)
        else:
            # If we are removing secrets, we should delete from keyring
            self.delete_secret(rpc_id)

        # 2. Update public part
        entry = {
            "id": rpc_id,
            "url": base_url if api_key else url,
            "note": rpc_data.get("note", ""),
            "encrypted": is_encrypted,
            "has_secrets": bool(api_key or secret_note),
        }

        custom_rpcs[cid_str][index] = entry
        config["custom_rpcs"] = custom_rpcs

        if is_global:
            self._save_toml(self.GLOBAL_CONFIG_FILE, config, is_global=True)
            self.global_config = config
        else:
            self._save_toml(self.LOCAL_CONFIG_FILE, config, is_global=False)
            self.local_config = config

    def _save_toml(self, path: Path, data: dict[str, Any], is_global: bool = False) -> None:
        """Save configuration to a TOML file with comments."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = tomlkit.document()
            title = "Global" if is_global else "Local Project"
            doc.add(tomlkit.comment(f"EVM RPC Picker - {title} Configuration"))
            doc.add(tomlkit.comment("This file stores favorites and custom RPCs."))
            doc.add(tomlkit.nl())

            for key, value in data.items():
                # For multiline strings, tomlkit handles them well if they contain \n
                doc[key] = value
                item = doc.get(key)
                if item is not None and hasattr(item, "comment"):
                    if key == "favorites":
                        item.comment("List of Chain IDs for pinned networks")
                    elif key == "custom_rpcs":
                        item.comment("Custom RPC endpoints")

            path.write_text(tomlkit.dumps(doc))
        except Exception:
            pass

    def local_config_exists(self) -> bool:
        """Check if local config file exists in CWD."""
        return self.LOCAL_CONFIG_FILE.exists()

    def global_config_exists(self) -> bool:
        """Check if global config file exists."""
        return self.GLOBAL_CONFIG_FILE.exists()

    def init_local_config(self) -> None:
        """Create an empty local config file."""
        if not self.local_config_exists():
            default_config: dict[str, Any] = {"favorites": [], "custom_rpcs": {}}
            self._save_toml(self.LOCAL_CONFIG_FILE, default_config)
            self.local_config = default_config
