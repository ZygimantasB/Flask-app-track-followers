"""
Encryption utilities for sensitive data.
Uses Fernet symmetric encryption from the cryptography library.
"""
import os
import base64
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import cryptography, provide fallback if not installed
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography library not installed. Encryption features disabled.")


# Key file location
KEY_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', '.encryption_key')


def generate_key() -> bytes:
    """Generate a new Fernet encryption key."""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError("cryptography library not installed")
    return Fernet.generate_key()


def derive_key_from_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using PBKDF2.
    Returns (key, salt) tuple.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise RuntimeError("cryptography library not installed")

    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def save_key(key: bytes, filepath: str = KEY_FILE) -> None:
    """Save encryption key to file with restricted permissions."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'wb') as f:
        f.write(key)

    # Set restrictive permissions (owner read/write only)
    try:
        os.chmod(filepath, 0o600)
    except OSError:
        # Windows doesn't support chmod in the same way
        pass

    logger.info(f"Encryption key saved to {filepath}")


def load_key(filepath: str = KEY_FILE) -> Optional[bytes]:
    """Load encryption key from file."""
    if not os.path.exists(filepath):
        return None

    with open(filepath, 'rb') as f:
        return f.read()


@lru_cache(maxsize=1)
def get_or_create_key() -> bytes:
    """Get existing key or create a new one."""
    key = load_key()
    if key is None:
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("cryptography library not installed")
        key = generate_key()
        save_key(key)
        logger.info("Generated new encryption key")
    return key


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Usage:
        service = EncryptionService()
        encrypted = service.encrypt("my_password")
        decrypted = service.decrypt(encrypted)
    """

    def __init__(self, key: bytes = None):
        """
        Initialize encryption service.

        Args:
            key: Optional encryption key. If not provided, will use/create default key.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            self._fernet = None
            logger.warning("Encryption disabled - cryptography library not installed")
            return

        if key is None:
            key = get_or_create_key()

        self._fernet = Fernet(key)

    @property
    def is_available(self) -> bool:
        """Check if encryption is available."""
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string, or original if encryption unavailable
        """
        if not self.is_available:
            logger.warning("Encryption not available, returning plaintext")
            return plaintext

        if not plaintext:
            return plaintext

        encrypted = self._fernet.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string.

        Args:
            ciphertext: The encrypted string to decrypt

        Returns:
            Decrypted plaintext string
        """
        if not self.is_available:
            logger.warning("Encryption not available, returning ciphertext")
            return ciphertext

        if not ciphertext:
            return ciphertext

        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode('utf-8')
        except (InvalidToken, ValueError) as e:
            # If decryption fails, the data might not be encrypted
            # This handles migration from unencrypted to encrypted data
            logger.warning(f"Decryption failed, assuming plaintext: {e}")
            return ciphertext

    def rotate_key(self, new_key: bytes = None) -> bytes:
        """
        Rotate to a new encryption key.

        Args:
            new_key: New key to use. If not provided, generates a new one.

        Returns:
            The new key
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("cryptography library not installed")

        if new_key is None:
            new_key = generate_key()

        save_key(new_key)
        self._fernet = Fernet(new_key)

        # Clear the cached key
        get_or_create_key.cache_clear()

        logger.info("Encryption key rotated")
        return new_key


# Global encryption service instance
encryption_service = EncryptionService()


def encrypt_sensitive_field(value: str) -> str:
    """Convenience function to encrypt a sensitive field."""
    return encryption_service.encrypt(value)


def decrypt_sensitive_field(value: str) -> str:
    """Convenience function to decrypt a sensitive field."""
    return encryption_service.decrypt(value)


# Database model mixin for encrypted fields
class EncryptedFieldMixin:
    """
    Mixin for SQLAlchemy models with encrypted fields.

    Usage:
        class MyModel(Base, EncryptedFieldMixin):
            _encrypted_fields = ['password', 'api_key']
            password = Column(String(500))
            api_key = Column(String(500))

        model = MyModel()
        model.set_encrypted('password', 'my_secret')
        print(model.get_decrypted('password'))  # 'my_secret'
    """

    _encrypted_fields: list = []

    def set_encrypted(self, field_name: str, value: str) -> None:
        """Set an encrypted field value."""
        if field_name not in self._encrypted_fields:
            raise ValueError(f"{field_name} is not an encrypted field")

        encrypted = encrypt_sensitive_field(value)
        setattr(self, field_name, encrypted)

    def get_decrypted(self, field_name: str) -> str:
        """Get a decrypted field value."""
        if field_name not in self._encrypted_fields:
            raise ValueError(f"{field_name} is not an encrypted field")

        encrypted = getattr(self, field_name, None)
        if encrypted is None:
            return None

        return decrypt_sensitive_field(encrypted)
