"""Verifica HMAC-SHA256 di Telegram.WebApp.initData.

Algoritmo ufficiale (https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app):
  1. secret_key = HMAC_SHA256(bot_token, "WebAppData")
  2. check_string = join ordinato per chiave (escludendo "hash") con "\n"
  3. Se HMAC_SHA256(secret_key, check_string).hex() != initData.hash -> rifiuta
  4. Opzionale: controlla auth_date (es. non più vecchio di 1 ora).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping
from urllib.parse import parse_qsl


def _parse_init_data(raw: str) -> dict[str, str]:
    return dict(parse_qsl(raw, keep_blank_values=True))


def verify_init_data(
    raw_init_data: str,
    bot_token: str,
    max_age_seconds: int = 3600,
) -> Mapping[str, str]:
    """Verifica initData firmato da Telegram.

    Returns: dict con i campi di initData se valido.
    Raises: ValueError se firma non valida o auth_date troppo vecchio.
    """
    if not raw_init_data or not bot_token:
        raise ValueError("init_data e bot_token sono obbligatori")

    data = _parse_init_data(raw_init_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("init_data senza campo hash")

    # 1. secret_key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # 2. check_string ordinato per chiave
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # 3. confronto HMAC
    calc_hash = hmac.new(
        key=secret_key,
        msg=check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise ValueError("Firma initData non valida")

    # 4. auth_date freshness (opzionale ma consigliato)
    auth_date = int(data.get("auth_date", "0"))
    if auth_date and (time.time() - auth_date) > max_age_seconds:
        raise ValueError("initData scaduto, riaprire la mini app")

    return data
