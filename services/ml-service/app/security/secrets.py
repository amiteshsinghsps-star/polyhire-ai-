"""
Secrets Management
==================
Loads secrets from environment variables in development,
HashiCorp Vault in production.

  Development:  .env file (gitignored)
  Production:   VAULT_ADDR + VAULT_TOKEN env vars → HashiCorp Vault

This is the ONLY place in the codebase where secrets are loaded.
Never call os.getenv() for secrets outside of this module.
"""

from __future__ import annotations
import os
import logging
from functools import lru_cache
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Secrets:
    gemini_api_key:          str
    groq_api_key:            str
    qdrant_api_key:          str
    qdrant_url:              str
    jwt_secret:              str
    embedding_signing_key:   str
    honeypot_secret:         str
    database_url:            str
    redis_url:               str
    pii_encryption_key:      str
    cors_allowed_origins:    str


class SecretsManager:
    """
    Unified secrets loader with Vault fallback.
    In development: reads .env via python-dotenv.
    In production:  reads from HashiCorp Vault KV v2 at path `secret/polyhire`.
    """

    def __init__(self) -> None:
        self._vault_client = None
        self._use_vault = bool(os.getenv("VAULT_ADDR") and os.getenv("VAULT_TOKEN"))
        if self._use_vault:
            self._init_vault()

    def _init_vault(self) -> None:
        try:
            import hvac  # type: ignore[import]
            self._vault_client = hvac.Client(
                url=os.environ["VAULT_ADDR"],
                token=os.environ["VAULT_TOKEN"],
            )
            if not self._vault_client.is_authenticated():
                raise RuntimeError("Vault authentication failed")
            logger.info("[Secrets] HashiCorp Vault connection established")
        except ImportError:
            logger.warning("[Secrets] hvac not installed — falling back to env vars")
            self._use_vault = False

    def _vault_get(self, key: str) -> str:
        secret = self._vault_client.secrets.kv.v2.read_secret_version(  # type: ignore[union-attr]
            path="polyhire", mount_point="secret",
        )
        return secret["data"]["data"].get(key, "")

    def _get(self, env_var: str, vault_key: str | None = None, required: bool = True) -> str:
        if self._use_vault and self._vault_client:
            try:
                value = self._vault_get(vault_key or env_var.lower())
                if value:
                    return value
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Secrets] Vault read failed for %s: %s", vault_key, exc)

        value = os.getenv(env_var, "")
        if required and not value:
            raise EnvironmentError(
                f"Required secret '{env_var}' is not set. "
                "Set it in .env (dev) or HashiCorp Vault (prod)."
            )
        return value

    @lru_cache(maxsize=1)
    def load(self) -> Secrets:
        return Secrets(
            gemini_api_key          = self._get("GEMINI_API_KEY",          "gemini_api_key",          required=False),
            groq_api_key            = self._get("GROQ_API_KEY",            "groq_api_key",            required=False),
            qdrant_api_key          = self._get("QDRANT_API_KEY",          "qdrant_api_key",          required=False),
            qdrant_url              = self._get("QDRANT_URL",              "qdrant_url",              required=False),
            jwt_secret              = self._get("JWT_SECRET",              "jwt_secret",              required=False),
            embedding_signing_key   = self._get("EMBEDDING_SIGNING_KEY",   "embedding_signing_key",   required=False),
            honeypot_secret         = self._get("HONEYPOT_SECRET",         "honeypot_secret",         required=False),
            database_url            = self._get("DATABASE_URL",            "database_url",            required=False),
            redis_url               = self._get("REDIS_URL",               "redis_url",               required=False),
            pii_encryption_key      = self._get("PII_ENCRYPTION_KEY",      "pii_key",                 required=False),
            cors_allowed_origins    = self._get("CORS_ALLOWED_ORIGINS",    "cors_allowed_origins",    required=False),
        )


# Singleton — import this everywhere
_manager = SecretsManager()
secrets  = _manager.load()
