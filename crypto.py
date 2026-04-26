"""
Token-Verschlüsselung für OAuth-Tokens in der Datenbank.
Nutzt Fernet (AES-128-CBC) mit einem Key aus der Umgebungsvariable ENCRYPTION_KEY.
Wenn kein Key gesetzt ist, werden Tokens im Klartext gespeichert (Fallback).
"""
import os
import logging
from base64 import urlsafe_b64encode
from hashlib import sha256

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
_fernet = None

if _ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        # Key aus beliebigem String ableiten (32 Bytes → Fernet-kompatibel)
        key = urlsafe_b64encode(sha256(_ENCRYPTION_KEY.encode()).digest())
        _fernet = Fernet(key)
        logger.info("Token-Verschlüsselung aktiv.")
    except ImportError:
        logger.warning("cryptography nicht installiert — Tokens werden im Klartext gespeichert.")
else:
    logger.info("ENCRYPTION_KEY nicht gesetzt — Tokens werden im Klartext gespeichert.")


def encrypt_token(token: str) -> str:
    """Verschlüsselt einen Token. Gibt Klartext zurück wenn keine Verschlüsselung aktiv."""
    if not token or not _fernet:
        return token
    try:
        return _fernet.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Verschlüsselung fehlgeschlagen: {e}")
        return token


def decrypt_token(token: str) -> str:
    """Entschlüsselt einen Token. Gibt Klartext zurück wenn keine Verschlüsselung aktiv."""
    if not token or not _fernet:
        return token
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        # Token war vermutlich nicht verschlüsselt (Migration von Klartext)
        return token
