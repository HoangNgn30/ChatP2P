"""
Tests for E2E encryption (RSA + AES).
"""

import pytest

from crypto.encryption import E2EEncryption
from crypto.key_manager import KeyManager


@pytest.fixture
def alice_keys():
    km = KeyManager("test_alice")
    km.generate_keys()
    return km


@pytest.fixture
def bob_keys():
    km = KeyManager("test_bob")
    km.generate_keys()
    return km


def test_encrypt_decrypt_roundtrip(alice_keys, bob_keys):
    """Message encrypted with Bob's public key should decrypt with Bob's private key."""
    plaintext = "Hello Bob! This is a secret message."

    encrypted = E2EEncryption.encrypt_message(plaintext, bob_keys.public_key)

    assert "content_encrypted" in encrypted
    assert "aes_key_encrypted" in encrypted
    assert "iv" in encrypted

    decrypted = E2EEncryption.decrypt_message(
        encrypted["content_encrypted"],
        encrypted["aes_key_encrypted"],
        encrypted["iv"],
        bob_keys.private_key,
    )

    assert decrypted == plaintext


def test_wrong_key_fails(alice_keys, bob_keys):
    """Decrypting with the wrong private key should raise an exception."""
    plaintext = "Secret for Bob only"
    encrypted = E2EEncryption.encrypt_message(plaintext, bob_keys.public_key)

    with pytest.raises(Exception):
        E2EEncryption.decrypt_message(
            encrypted["content_encrypted"],
            encrypted["aes_key_encrypted"],
            encrypted["iv"],
            alice_keys.private_key,  # Wrong key!
        )


def test_unicode_content(bob_keys):
    """Unicode / emoji content should survive encryption round-trip."""
    plaintext = "Xin chào 🇻🇳! Tin nhắn mã hóa 🔐"
    encrypted = E2EEncryption.encrypt_message(plaintext, bob_keys.public_key)
    decrypted = E2EEncryption.decrypt_message(
        encrypted["content_encrypted"],
        encrypted["aes_key_encrypted"],
        encrypted["iv"],
        bob_keys.private_key,
    )
    assert decrypted == plaintext


def test_empty_message(bob_keys):
    """Even an empty string should encrypt/decrypt correctly."""
    encrypted = E2EEncryption.encrypt_message("", bob_keys.public_key)
    decrypted = E2EEncryption.decrypt_message(
        encrypted["content_encrypted"],
        encrypted["aes_key_encrypted"],
        encrypted["iv"],
        bob_keys.private_key,
    )
    assert decrypted == ""


def test_long_message(bob_keys):
    """A long message (multi-block AES) should work."""
    plaintext = "A" * 10_000
    encrypted = E2EEncryption.encrypt_message(plaintext, bob_keys.public_key)
    decrypted = E2EEncryption.decrypt_message(
        encrypted["content_encrypted"],
        encrypted["aes_key_encrypted"],
        encrypted["iv"],
        bob_keys.private_key,
    )
    assert decrypted == plaintext


def test_key_manager_pem_roundtrip(alice_keys):
    """Public key PEM export/import should preserve the key."""
    pem = alice_keys.get_public_key_pem()
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")

    km2 = KeyManager("test_other")
    km2.generate_keys()
    km2.add_peer_public_key("alice", pem)

    restored = km2.get_peer_public_key("alice")
    assert restored is not None

    # Encrypt with restored key, decrypt with original private key
    msg = "Test with restored key"
    enc = E2EEncryption.encrypt_message(msg, restored)
    dec = E2EEncryption.decrypt_message(
        enc["content_encrypted"],
        enc["aes_key_encrypted"],
        enc["iv"],
        alice_keys.private_key,
    )
    assert dec == msg
