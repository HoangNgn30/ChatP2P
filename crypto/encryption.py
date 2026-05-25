"""
End-to-end encryption using RSA + AES.

Sender:
    1. Generate random AES-256 key and 128-bit IV
    2. Encrypt plaintext with AES-CBC
    3. Encrypt AES key with recipient's RSA public key (OAEP)
    4. Send {content_encrypted, aes_key_encrypted, iv} (all base64)

Receiver:
    1. Decrypt AES key with own RSA private key
    2. Decrypt content with AES key + IV
"""

import base64
import os

from cryptography.hazmat.primitives import hashes, padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from utils.constants import AES_IV_SIZE, AES_KEY_SIZE
from utils.logger import get_logger

log = get_logger(__name__)


class E2EEncryption:
    """Stateless helper for RSA+AES hybrid encryption."""

    # ── encrypt ────────────────────────────────────────────

    @staticmethod
    def encrypt_message(plaintext: str, recipient_public_key) -> dict:
        """
        Encrypt *plaintext* for *recipient_public_key*.

        Returns a dict with base64-encoded strings::

            {
                "content_encrypted": "...",
                "aes_key_encrypted": "...",
                "iv": "..."
            }
        """
        # 1. Random AES key and IV
        aes_key = os.urandom(AES_KEY_SIZE)
        iv = os.urandom(AES_IV_SIZE)

        # 2. AES-CBC encrypt (with PKCS7 padding)
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        content_encrypted = encryptor.update(padded) + encryptor.finalize()

        # 3. RSA-OAEP encrypt the AES key
        aes_key_encrypted = recipient_public_key.encrypt(
            aes_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return {
            "content_encrypted": base64.b64encode(content_encrypted).decode(),
            "aes_key_encrypted": base64.b64encode(aes_key_encrypted).decode(),
            "iv": base64.b64encode(iv).decode(),
        }

    # ── decrypt ────────────────────────────────────────────

    @staticmethod
    def decrypt_message(
        content_encrypted: str,
        aes_key_encrypted: str,
        iv: str,
        private_key,
    ) -> str:
        """
        Decrypt a message.  All inputs are base64-encoded strings.
        Returns the plaintext.
        """
        # 1. Decode base64
        content_bytes = base64.b64decode(content_encrypted)
        aes_key_bytes = base64.b64decode(aes_key_encrypted)
        iv_bytes = base64.b64decode(iv)

        # 2. RSA-OAEP decrypt the AES key
        aes_key = private_key.decrypt(
            aes_key_bytes,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # 3. AES-CBC decrypt
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv_bytes))
        decryptor = cipher.decryptor()
        padded = decryptor.update(content_bytes) + decryptor.finalize()

        # 4. Remove PKCS7 padding
        unpadder = sym_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        return plaintext.decode("utf-8")

    # ── signatures ─────────────────────────────────────────

    @staticmethod
    def sign_message(data: str, private_key) -> str:
        """
        Sign *data* using RSA-PSS and SHA-256.
        Returns the signature as a base64 string.
        """
        signature = private_key.sign(
            data.encode("utf-8"),
            asym_padding.PSS(
                mgf=asym_padding.MGF1(hashes.SHA256()),
                salt_length=asym_padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify_signature(data: str, signature_b64: str, public_key) -> bool:
        """
        Verify the base64 *signature_b64* of *data* using the sender's public key.
        Returns True if valid, False otherwise.
        """
        try:
            signature = base64.b64decode(signature_b64)
            public_key.verify(
                signature,
                data.encode("utf-8"),
                asym_padding.PSS(
                    mgf=asym_padding.MGF1(hashes.SHA256()),
                    salt_length=asym_padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as exc:
            log.warning("Signature verification failed: %s", exc)
            return False
