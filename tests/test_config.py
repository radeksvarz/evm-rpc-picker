import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evm_rpc_picker.config import ConfigManager, EncryptionManager


@pytest.fixture
def temp_config(tmp_path):
    """Fixture to mock config paths and return a ConfigManager instance."""
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    local_file = tmp_path / "local" / ".rpc-picker.toml"
    local_file.parent.mkdir()

    # We need to patch the class attributes and the platformdirs call
    with (
        patch("evm_rpc_picker.config.user_config_dir", return_value=str(global_dir)),
        patch("evm_rpc_picker.config.ConfigManager.LOCAL_CONFIG_FILE", local_file),
        patch(
            "evm_rpc_picker.config.ConfigManager.GLOBAL_CONFIG_FILE",
            global_dir / "config.toml",
        ),
    ):
        cm = ConfigManager()
        yield cm, global_dir, local_file


def test_load_save_toml(temp_config):
    cm, global_dir, _ = temp_config

    # Test saving and loading
    data = {"test": 123, "note": "Multi\nLine"}
    test_path = global_dir / "test.toml"
    cm._save_toml(test_path, data)
    loaded = cm._load_toml(test_path)
    assert loaded["test"] == 123
    assert loaded["note"] == "Multi\nLine"

    # Test loading non-existent
    assert cm._load_toml(global_dir / "missing.toml") == {}

    # Test invalid TOML
    invalid_file = global_dir / "invalid.toml"
    invalid_file.write_text("invalid = [")
    assert cm._load_toml(invalid_file) == {}


def test_toml_multiline_format(temp_config):
    cm, global_dir, _ = temp_config

    # Add an RPC with a multiline note
    cm.add_custom_rpc(1, {"url": "http://test.com", "note": "line1\nline2\nline3"}, is_global=True)

    # Read the file directly to verify formatting
    content = cm.GLOBAL_CONFIG_FILE.read_text()

    # Verify it is written as an array of tables (not inline dictionaries)
    assert "[[custom_rpcs.1]]" in content
    # Verify multiline string formatting
    assert 'note = """line1\nline2\nline3"""' in content


def test_favorites(temp_config):
    cm, _, _ = temp_config

    # Global toggle
    cm.toggle_favorite(1, is_global=True)
    assert 1 in cm.get_favorites()
    assert 1 in cm.get_favorites(project_only=False)
    assert 1 not in cm.get_favorites(project_only=True)

    # Local toggle
    cm.toggle_favorite(137, is_global=False)
    assert 137 in cm.get_favorites()
    assert 137 in cm.get_favorites(project_only=True)

    # Untoggle
    cm.toggle_favorite(1, is_global=True)
    assert 1 not in cm.get_favorites()

    # Favorite RPCs
    cm.toggle_favorite_rpc("http://test", is_global=True)
    assert "http://test" in cm.get_favorite_rpcs()
    assert "http://test" in cm.get_favorite_rpcs(project_only=False)
    assert "http://test" not in cm.get_favorite_rpcs(project_only=True)
    
    # Untoggle RPC
    cm.toggle_favorite_rpc("http://test", is_global=True)
    assert "http://test" not in cm.get_favorite_rpcs()

    # Local toggle RPC
    cm.toggle_favorite_rpc("http://local", is_global=False)
    assert "http://local" in cm.get_favorite_rpcs()
    cm.toggle_favorite_rpc("http://local", is_global=False)
    assert "http://local" not in cm.get_favorite_rpcs()

def test_config_exists_and_schema_update(temp_config):
    cm, global_dir, local_file = temp_config
    
    # Create the global file
    cm.GLOBAL_CONFIG_FILE.write_text("[favorite_chains]\n")
    
    # Test global_config_exists
    assert cm.global_config_exists() == True
    
    # Test schema upgrade manually
    old_config = {"favorite_chains": []}
    cm._ensure_schema_version(old_config, cm.GLOBAL_CONFIG_FILE, is_global=True)
    assert old_config.get("schema_version") == cm.CURRENT_SCHEMA_VERSION

def test_keyring_wrapper(temp_config):
    cm, _, _ = temp_config
    
    with patch("keyring.set_password") as mock_set:
        cm.set_secret("test_key", "test_val")
        mock_set.assert_called_once_with(cm.APP_NAME, "test_key", "test_val")
        
    with patch("keyring.get_password", return_value="test_val") as mock_get:
        assert cm.get_secret("test_key") == "test_val"
        mock_get.assert_called_once_with(cm.APP_NAME, "test_key")
        
    with patch("keyring.delete_password") as mock_del:
        cm.delete_secret("test_key")
        mock_del.assert_called_once_with(cm.APP_NAME, "test_key")
        
    import keyring
    with patch("keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError):
        # Should catch and pass
        cm.delete_secret("test_key")

def test_save_toml_exception(temp_config):
    cm, global_dir, _ = temp_config
    test_path = global_dir / "test2.toml"
    
    # Force an exception by passing an object that tomlkit cannot serialize
    class Unserializable:
        pass
        
    cm._save_toml(test_path, {"bad": Unserializable()})
    assert not test_path.exists()


def test_encryption_manager():
    password = "test-password"
    data = "secret-message"

    # Encrypt
    blob, salt = EncryptionManager.encrypt(data, password)
    assert blob != data

    # Decrypt
    decrypted = EncryptionManager.decrypt(blob, salt, password)
    assert decrypted == data

    # Wrong password
    assert EncryptionManager.decrypt(blob, salt, "wrong") is None

    # Invalid salt/blob
    assert EncryptionManager.decrypt("invalid", "invalid", password) is None


def test_smart_extract_key():
    cm = ConfigManager()

    # Infura
    url = "https://mainnet.infura.io/v3/secret123"
    base, key = cm.smart_extract_key(url)
    assert base == "https://mainnet.infura.io/v3/${API_KEY}"
    assert key == "secret123"

    # Alchemy
    url = "https://eth-mainnet.g.alchemy.com/v2/secret456"
    base, key = cm.smart_extract_key(url)
    assert base == "https://eth-mainnet.g.alchemy.com/v2/${API_KEY}"
    assert key == "secret456"

    # No key
    url = "https://rpc.ankr.com/eth"
    base, key = cm.smart_extract_key(url)
    assert base == url
    assert key == ""


def test_rpc_secrets(temp_config):
    cm, _, _ = temp_config

    with (
        patch("keyring.set_password") as mock_set,
        patch("keyring.get_password") as mock_get,
    ):
        # 1. Standard (not encrypted)
        cm.save_rpc_secret("rpc1", "key1", "note1")
        args, _ = mock_set.call_args
        saved_data = json.loads(args[2])
        assert saved_data["api_key"] == "key1"
        assert not saved_data["encrypted"]

        mock_get.return_value = json.dumps(saved_data)
        loaded = cm.load_rpc_secret("rpc1")
        assert loaded["api_key"] == "key1"
        assert loaded["status"] == "ok"

        # 2. Encrypted
        cm.save_rpc_secret("rpc2", "key2", "note2", password="p")
        args, _ = mock_set.call_args
        saved_data = json.loads(args[2])
        assert saved_data["encrypted"]

        mock_get.return_value = json.dumps(saved_data)
        # Needs password
        assert cm.load_rpc_secret("rpc2")["status"] == "needs_password"

        # Correct password
        loaded = cm.load_rpc_secret("rpc2", password="p")
        assert loaded["api_key"] == "key2"
        assert loaded["status"] == "ok"

        # Wrong password
        assert cm.load_rpc_secret("rpc2", password="wrong")["status"] == "wrong_password"


def test_delete_secret(temp_config):
    cm, _, _ = temp_config
    with patch("keyring.delete_password") as mock_del:
        cm.delete_secret("rpc1")
        mock_del.assert_called_once()


def test_delete_secret_error(temp_config):
    cm, _, _ = temp_config
    import keyring

    with patch("keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError):
        cm.delete_secret("rpc1")
        # Should not raise


def test_add_custom_rpc_public(temp_config):
    cm, _, _ = temp_config
    rpc_data = {"url": "https://rpc.example.com", "note": "Public"}
    cm.add_custom_rpc(1, rpc_data, is_global=True)

    custom = cm.get_custom_rpcs(1)
    assert len(custom) == 1
    assert custom[0]["url"] == "https://rpc.example.com"
    assert custom[0]["has_secrets"] is False
    assert cm.global_config["custom_rpcs"]["1"][0]["url"] == "https://rpc.example.com"


def test_add_custom_rpc_with_secrets(temp_config):
    cm, _, _ = temp_config
    rpc_data = {
        "url": "https://mainnet.infura.io/v3/secret123",
        "secret_note": "My secret note",
    }
    # Mock keyring to avoid system calls
    with patch("keyring.set_password") as mock_set:
        cm.add_custom_rpc(1, rpc_data, is_global=False)
        mock_set.assert_called_once()

    custom = cm.get_custom_rpcs(1)
    assert len(custom) == 1
    assert custom[0]["url"] == "https://mainnet.infura.io/v3/${API_KEY}"
    assert custom[0]["has_secrets"] is True


def test_update_custom_rpc(temp_config):
    cm, _, _ = temp_config
    rpc_data = {"url": "https://rpc.example.com", "note": "Original"}
    cm.add_custom_rpc(1, rpc_data, is_global=False)

    rpc_id = cm.get_custom_rpcs(1)[0]["id"]
    new_data = {"url": "https://new-rpc.com", "note": "Updated"}
    cm.update_custom_rpc(1, rpc_id, new_data, is_global=False)

    custom = cm.get_custom_rpcs(1)
    assert len(custom) == 1
    assert custom[0]["url"] == "https://new-rpc.com"
    assert custom[0]["note"] == "Updated"


def test_save_toml_error(temp_config):
    cm, _, _ = temp_config
    with patch("pathlib.Path.mkdir", side_effect=IOError):
        cm._save_toml(Path("any_path"), {"data": 1})


def test_init_local_config(temp_config):
    cm, _, local_file = temp_config
    if local_file.exists():
        local_file.unlink()

    cm.init_local_config()
    assert local_file.exists()
    assert cm.local_config["favorite_chains"] == []


def test_update_custom_rpc_errors(temp_config):
    cm, _, _ = temp_config
    # Chain ID not found
    cm.update_custom_rpc(999, "any", {})

    # RPC ID not found
    cm.add_custom_rpc(1, {"url": "http://test.com"})
    cm.update_custom_rpc(1, "non-existent", {})


def test_update_global_rpc_with_secrets(temp_config):
    cm, _, _ = temp_config
    # 1. Add global RPC
    cm.add_custom_rpc(1, {"url": "http://old.com"}, is_global=True)
    rpc_id = cm.get_custom_rpcs(1)[0]["id"]

    # 2. Update to have secrets
    new_data = {"url": "https://infura.io/v3/key123", "secret_note": "secret"}
    with patch("keyring.set_password") as mock_set:
        cm.update_custom_rpc(1, rpc_id, new_data, is_global=True)
        mock_set.assert_called_once()

    custom = cm.get_custom_rpcs(1)
    assert custom[0]["url"] == "https://infura.io/v3/${API_KEY}"
    assert custom[0]["source"] == "global"


def test_load_rpc_secret_missing_and_error(temp_config):
    cm, _, _ = temp_config
    with patch("keyring.get_password", return_value=None):
        assert cm.load_rpc_secret("missing") == {}

    with patch("keyring.get_password", return_value="invalid-json"):
        assert cm.load_rpc_secret("error")["status"] == "error"
