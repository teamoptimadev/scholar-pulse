"""Application configuration from environment variables."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLACEHOLDER_KEY = "change-me-in-production"

logger = logging.getLogger(__name__)


def resolve_environment(raw: str | None) -> str:
    """Return a validated environment name (development, test, or production)."""
    if raw is None:
        return "development"
    value = raw.strip().lower()
    allowed = {"development", "test", "production"}
    if value not in allowed:
        raise ValueError(
            f"ENVIRONMENT must be one of {sorted(allowed)}, got {value!r}"
        )
    return value


def resolve_cookie_secure(environment: str, raw: str | None) -> bool:
    """Derive COOKIE_SECURE from the env var or fall back to environment."""
    if raw is not None:
        normalised = raw.strip().lower()
        if normalised == "true":
            return True
        if normalised == "false":
            if environment == "production":
                logger.warning(
                    "COOKIE_SECURE is explicitly false in production — "
                    "cookies will be sent over plain HTTP"
                )
            return False
        raise ValueError(
            f"COOKIE_SECURE must be 'true' or 'false', got {raw!r}"
        )
    return environment == "production"


def validate_secret_key(environment: str, key: str) -> str:
    """Validate SECRET_KEY and return it. Raises in production for weak keys."""
    if environment == "production":
        if key == _PLACEHOLDER_KEY or len(key.encode()) < 32:
            raise RuntimeError(
                "SECRET_KEY must be at least 32 bytes and not the default "
                "placeholder in production. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_hex(32))"'
            )
    else:
        if key == _PLACEHOLDER_KEY or len(key.encode()) < 32:
            logger.warning(
                "SECRET_KEY is weak (%d bytes); acceptable in %s but not production",
                len(key.encode()),
                environment,
            )
    return key


class Settings:
    """Application settings loaded from environment."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://prj649:prj649_dev@localhost:5432/academic_analytics",
    )
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
    ML_MODELS_DIR: str = os.getenv(
        "ML_MODELS_DIR",
        str(_REPO_ROOT / "ml" / "models"),
    )

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    JWT_ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000"
    ).split(",")

    # Observability
    SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")

    # Validated settings
    ENVIRONMENT: str = resolve_environment(os.getenv("ENVIRONMENT"))
    SECRET_KEY: str = validate_secret_key(
        ENVIRONMENT, os.getenv("SECRET_KEY", _PLACEHOLDER_KEY)
    )
    COOKIE_SECURE: bool = resolve_cookie_secure(
        ENVIRONMENT, os.getenv("COOKIE_SECURE")
    )


settings = Settings()
