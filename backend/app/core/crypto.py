from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _build_fernet() -> Fernet:
    settings = get_settings()
    seed = settings.app_encryption_key or settings.secret_key
    digest = sha256(seed.encode("utf-8")).digest()
    return Fernet(urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    fernet = _build_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    fernet = _build_fernet()
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
