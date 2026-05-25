"""
RSA key-pair management – generate, save, load, and exchange.
"""

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from utils.constants import RSA_KEY_SIZE
from utils.logger import get_logger

log = get_logger(__name__)


class KeyManager:
    """
    Manages the local RSA key-pair and caches public keys of remote peers.

    Keys are stored on disk under ``keys/<username>/``.
    """

    def __init__(self, username: str) -> None:
        self.username = username
        self.keys_dir = Path("keys") / username
        self.private_key = None
        self.public_key = None
        self.peer_public_keys: dict[str, object] = {}  # username → RSA public key

    # ── key generation ─────────────────────────────────────

    def generate_keys(self) -> None:
        """Generate a fresh RSA key-pair."""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
        )
        self.public_key = self.private_key.public_key()
        log.info("RSA-%d key-pair generated for %s", RSA_KEY_SIZE, self.username)

    # ── persistence ────────────────────────────────────────

    def save_keys(self) -> None:
        """Write the key-pair to PEM files."""
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        priv_path = self.keys_dir / "private.pem"
        pub_path = self.keys_dir / "public.pem"

        priv_path.write_bytes(
            self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        pub_path.write_bytes(
            self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        log.info("Keys saved to %s", self.keys_dir)

    def load_keys(self) -> bool:
        """
        Load existing keys from disk.
        Returns True on success, False if files don't exist.
        """
        priv_path = self.keys_dir / "private.pem"
        pub_path = self.keys_dir / "public.pem"

        if not priv_path.exists() or not pub_path.exists():
            return False

        self.private_key = serialization.load_pem_private_key(
            priv_path.read_bytes(),
            password=None,
        )
        self.public_key = serialization.load_pem_public_key(pub_path.read_bytes())
        log.info("Keys loaded from %s", self.keys_dir)
        return True

    def load_or_generate(self) -> None:
        """Load existing keys or generate new ones."""
        if not self.load_keys():
            self.generate_keys()
            self.save_keys()

    # ── PEM serialisation ──────────────────────────────────

    def get_public_key_pem(self) -> str:
        """Return the public key as a PEM-encoded string."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    # ── peer keys ──────────────────────────────────────────

    def add_peer_public_key(self, username: str, public_key_pem: str) -> None:
        """Store a peer's public key (from PEM string)."""
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        self.peer_public_keys[username] = key
        log.debug("Stored public key for peer: %s", username)

    def get_peer_public_key(self, username: str):
        """Return the cached RSA public key object for *username*, or None."""
        return self.peer_public_keys.get(username)
