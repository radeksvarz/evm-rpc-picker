import json
import time
from collections.abc import Iterable
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
    CURRENT_SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self.global_config: dict[str, Any] = self._load_toml(self.GLOBAL_CONFIG_FILE)
        self.local_config: dict[str, Any] = self._load_toml(self.LOCAL_CONFIG_FILE)
        self.encryption_manager = EncryptionManager()

        self._ensure_schema_version(self.global_config, self.GLOBAL_CONFIG_FILE, is_global=True)
        if self.local_config_exists():
            self._ensure_schema_version(self.local_config, self.LOCAL_CONFIG_FILE, is_global=False)

    def _ensure_schema_version(self, config: dict[str, Any], path: Path, is_global: bool) -> None:
        """Ensure the config has the current schema version and save it if needed."""
        if path.exists() and config.get("schema_version") != self.CURRENT_SCHEMA_VERSION:
            config["schema_version"] = self.CURRENT_SCHEMA_VERSION
            self._save_toml(path, config, is_global=is_global)

    def _load_toml(self, path: Path) -> dict[str, Any]:
        """Load configuration from a TOML file."""
        if path.exists():
            try:
                # Use tomlkit to preserve structure/comments for later
                parsed = cast(dict[str, Any], dict(tomlkit.parse(path.read_text())))
                if "favorites" in parsed:
                    favs = parsed["favorites"]
                    if isinstance(favs, dict):
                        if "favorite_chains" in favs:
                            parsed["favorite_chains"] = list(
                                cast(Iterable[Any], favs["favorite_chains"])
                            )
                        if "favorite_rpcs" in favs:
                            parsed["favorite_rpcs"] = [str(x) for x in favs["favorite_rpcs"]]
                return parsed
            except Exception:
                return {}
        return {}

    # --- Favorites ---

    def get_favorites(self, project_only: bool = False) -> set[int]:
        """Get a set of favorite chain IDs from both configs or just local."""
        favorites = set(self.local_config.get("favorite_chains", []))
        if not project_only:
            favorites.update(self.global_config.get("favorite_chains", []))
        return favorites

    def toggle_favorite(self, chain_id: int, is_global: bool = False) -> None:
        """Toggle a favorite chain ID in the specified config. Auto-creates file if missing."""
        config = self.global_config if is_global else self.local_config
        path = self.GLOBAL_CONFIG_FILE if is_global else self.LOCAL_CONFIG_FILE

        favorites = list(config.get("favorite_chains", []))
        if chain_id in favorites:
            favorites.remove(chain_id)
        else:
            favorites.append(chain_id)

        config["favorite_chains"] = favorites
        self._save_toml(path, config, is_global=is_global)

        # Update internal state
        if is_global:
            self.global_config = config
        else:
            self.local_config = config

    def get_favorite_rpcs(self, project_only: bool = False) -> set[str]:
        """Get a set of favorite RPC URLs from both configs or just local."""
        favorites = set(self.local_config.get("favorite_rpcs", []))
        if not project_only:
            favorites.update(self.global_config.get("favorite_rpcs", []))
        return favorites

    def toggle_favorite_rpc(self, url: str, is_global: bool = False) -> None:
        """Toggle a favorite RPC URL in the specified config."""
        config = self.global_config if is_global else self.local_config
        path = self.GLOBAL_CONFIG_FILE if is_global else self.LOCAL_CONFIG_FILE

        favorites = list(config.get("favorite_rpcs", []))
        url = url.strip()
        if url in favorites:
            favorites.remove(url)
        else:
            favorites.append(url)

        config["favorite_rpcs"] = favorites
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

    @staticmethod
    def resolve_url_secrets(url: str, key_name: str, secret_value: str) -> str:
        """Resolve secret placeholders in URL."""
        resolved = url.replace("${API_KEY}", secret_value)
        resolved = resolved.replace(f"{{{{secret:{key_name}}}}}", secret_value)
        return resolved

    @staticmethod
    def mask_url_secrets(url: str, key_name: str) -> str:
        """Mask secret placeholders in URL for display."""
        masked = url.replace("${API_KEY}", "********")
        masked = masked.replace(f"{{{{secret:{key_name}}}}}", "********")
        return masked

    @staticmethod
    def normalize_custom_rpc(rpc: dict[str, Any]) -> dict[str, Any]:
        """Normalize a custom RPC dict to ensure compatibility with old and new schemas."""
        item = dict(rpc)

        # Normalize password protection flag
        if "rpc_password_protected" in item:
            item["encrypted"] = item["rpc_password_protected"]
        elif "encrypted" in item:
            item["rpc_password_protected"] = item["encrypted"]
        else:
            item["rpc_password_protected"] = False
            item["encrypted"] = False

        url = item.get("url", "")
        # Check if URL contains placeholders
        has_secret_placeholder = "{{secret:" in url or "${API_KEY}" in url

        # Normalize note_in_keyring flag
        if "note_in_keyring" not in item:
            item["note_in_keyring"] = item.get("has_secrets", False) and not has_secret_placeholder

        # Populate has_secrets for backward compatibility
        has_sec = item.get("has_secrets", False)
        has_note = item.get("note_in_keyring", False)
        item["has_secrets"] = has_sec or has_note or has_secret_placeholder
        return item

    def get_custom_rpcs(self, chain_id: int) -> list[dict[str, Any]]:
        """Get custom RPCs for a chain from both configs."""
        # Merge global and local custom RPCs
        global_rpcs = [
            dict(r) for r in self.global_config.get("custom_rpcs", {}).get(str(chain_id), [])
        ]
        local_rpcs = [
            dict(r) for r in self.local_config.get("custom_rpcs", {}).get(str(chain_id), [])
        ]

        # Tag them for UI differentiation
        for rpc in global_rpcs:
            rpc["source"] = "global"
            rpc.update(self.normalize_custom_rpc(rpc))
        for rpc in local_rpcs:
            rpc["source"] = "project"
            rpc.update(self.normalize_custom_rpc(rpc))

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

        if api_key:
            config_url = base_url.replace("${API_KEY}", f"{{{{secret:{rpc_id}}}}}")
        else:
            config_url = url

        entry = {
            "id": rpc_id,
            "name": rpc_data.get("name", ""),
            "url": config_url,
            "note": rpc_data.get("note", ""),
            "network_type": rpc_data.get("network_type", "Production"),
            "rpc_password_protected": is_encrypted,
            "note_in_keyring": bool(secret_note),
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
        if api_key:
            config_url = base_url.replace("${API_KEY}", f"{{{{secret:{rpc_id}}}}}")
        else:
            config_url = url

        entry = {
            "id": rpc_id,
            "name": rpc_data.get("name", ""),
            "url": config_url,
            "note": rpc_data.get("note", ""),
            "network_type": rpc_data.get("network_type", "Production"),
            "rpc_password_protected": is_encrypted,
            "note_in_keyring": bool(secret_note),
        }

        custom_rpcs[cid_str][index] = entry
        config["custom_rpcs"] = custom_rpcs
        if is_global:
            self._save_toml(self.GLOBAL_CONFIG_FILE, config, is_global=True)
            self.global_config = config
        else:
            self._save_toml(self.LOCAL_CONFIG_FILE, config, is_global=False)
            self.local_config = config

    def delete_custom_rpc(self, chain_id: int, rpc_id: str, is_global: bool = False) -> None:
        """Delete a custom RPC from the specified config."""
        config = self.global_config if is_global else self.local_config
        custom_rpcs = config.get("custom_rpcs", {})
        cid_str = str(chain_id)

        if cid_str not in custom_rpcs:
            return

        # Filter out the RPC with the matching ID
        custom_rpcs[cid_str] = [rpc for rpc in custom_rpcs[cid_str] if rpc["id"] != rpc_id]

        # If no RPCs left for this chain, remove the chain entry
        if not custom_rpcs[cid_str]:
            del custom_rpcs[cid_str]

        config["custom_rpcs"] = custom_rpcs
        if is_global:
            self._save_toml(self.GLOBAL_CONFIG_FILE, config, is_global=True)
            self.global_config = config
        else:
            self._save_toml(self.LOCAL_CONFIG_FILE, config)
            self.local_config = config

        # Also cleanup secret if exists
        self.delete_secret(rpc_id)

    def _save_toml(self, path: Path, data: dict[str, Any], is_global: bool = False) -> None:
        """Save configuration to a TOML file with comments and precise ordering."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = tomlkit.document()
            title = "Global" if is_global else "Local Project"
            doc.add(tomlkit.comment(f"EVM RPC Picker - {title} Configuration"))
            doc.add(tomlkit.comment("This file stores favorites and custom RPCs."))
            doc.add(tomlkit.nl())

            # 1. schema_version is part of the header of the file (just below header comments)
            doc.add(
                tomlkit.comment(f"Config schema version (current: {self.CURRENT_SCHEMA_VERSION})")
            )
            doc.add("schema_version", data.get("schema_version", self.CURRENT_SCHEMA_VERSION))
            doc.add(tomlkit.nl())

            # 2. [favorites] section
            fav_table = tomlkit.table()

            # 2.1 favorite_chains
            fav_table.add(tomlkit.comment("List of Chain IDs for pinned networks"))
            chains = data.get("favorite_chains", [])
            chains_arr = tomlkit.array()
            for chain in chains:
                chains_arr.append(chain)
            if len(chains) > 0:
                chains_arr.multiline(True)
            fav_table.add("favorite_chains", chains_arr)
            fav_table.add(tomlkit.nl())

            # 2.2 favorite_rpcs
            fav_table.add(tomlkit.comment("List of favorite RPC URLs"))
            rpcs = data.get("favorite_rpcs", [])
            rpcs_arr = tomlkit.array()
            for rpc in rpcs:
                rpcs_arr.append(rpc)
            if len(rpcs) > 0:
                rpcs_arr.multiline(True)
            fav_table.add("favorite_rpcs", rpcs_arr)

            doc.add("favorites", fav_table)
            doc.add(tomlkit.nl())

            # 3. custom_rpcs sections
            custom_rpcs = data.get("custom_rpcs", {})
            if custom_rpcs:
                doc.add(tomlkit.comment("Custom RPC endpoints"))
                doc.add("custom_rpcs", self._build_custom_rpcs_table(custom_rpcs))
                doc.add(tomlkit.nl())

            # Write other custom/unexpected root keys (if any)
            for k, v in data.items():
                if k not in (
                    "schema_version",
                    "favorite_chains",
                    "favorite_rpcs",
                    "custom_rpcs",
                    "favorites",
                ):
                    doc.add(k, v)

            path.write_text(tomlkit.dumps(doc))
        except Exception:
            pass

    def _build_custom_rpcs_table(
        self, custom_rpcs: dict[str, list[dict[str, Any]]]
    ) -> tomlkit.items.Table:
        """Build a TOML table for custom RPCs."""
        rpc_table = tomlkit.table()
        for chain_id_str, rpcs in custom_rpcs.items():
            aot = tomlkit.aot()
            for rpc in rpcs:
                t = tomlkit.table()
                t.indent(2)
                for k, v in rpc.items():
                    if isinstance(v, str) and "\n" in v:
                        t.add(k, tomlkit.string(v, multiline=True))
                    else:
                        t.add(k, v)
                aot.append(t)
            rpc_table.add(chain_id_str, aot)
        return rpc_table

    def local_config_exists(self) -> bool:
        """Check if local config file exists in CWD."""
        return self.LOCAL_CONFIG_FILE.exists()

    def global_config_exists(self) -> bool:
        """Check if global config file exists."""
        return self.GLOBAL_CONFIG_FILE.exists()

    def init_local_config(self) -> None:
        """Create an empty local config file."""
        if not self.local_config_exists():
            default_config: dict[str, Any] = {
                "schema_version": self.CURRENT_SCHEMA_VERSION,
                "favorite_chains": [],
                "favorite_rpcs": [],
                "custom_rpcs": {},
            }
            self._save_toml(self.LOCAL_CONFIG_FILE, default_config)
            self.local_config = default_config
