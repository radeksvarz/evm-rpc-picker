import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """Handles encryption and decryption of secrets using user-provided passwords."""

    ITERATIONS = 100_000

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive a cryptographic key from a password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=EncryptionManager.ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    @staticmethod
    def encrypt(data: str, password: str) -> tuple[str, str]:
        """Encrypt data with a password. Returns (encrypted_blob_b64, salt_b64)."""
        salt = os.urandom(16)
        key = EncryptionManager.derive_key(password, salt)
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(data.encode())
        return (
            base64.b64encode(encrypted_data).decode(),
            base64.b64encode(salt).decode(),
        )

    @staticmethod
    def decrypt(encrypted_blob_b64: str, salt_b64: str, password: str) -> str | None:
        """Decrypt data with a password and salt. Returns None if decryption fails."""
        try:
            salt = base64.b64decode(salt_b64)
            key = EncryptionManager.derive_key(password, salt)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(base64.b64decode(encrypted_blob_b64))
            return decrypted_data.decode()
        except Exception:
            return None
