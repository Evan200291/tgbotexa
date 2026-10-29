"""Typed configuration loaded from environment / .env.

Secrets are SecretStr so they never appear in repr(), logs or tracebacks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when configuration is unsafe or incomplete."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr = SecretStr("")
    # NoDecode: we parse "1,2,3" ourselves instead of pydantic expecting JSON.
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=lambda: [1877867098])

    # The base URL embeds the panel's secret web path, so it is a secret too.
    panel_base_url: SecretStr = SecretStr("")
    panel_user: SecretStr = SecretStr("")
    panel_pass: SecretStr = SecretStr("")
    panel_verify_tls: bool = True
    inbound_remark: str = "exabytetgbot"
    server_host: str = "tpone.lhpvpn.online"

    bot_domain: str = "tgbot.lhpvpn.online"
    support_url: str = "https://t.me/Exabytedigitals"

    kbz_number: str = ""
    kbz_name: str = ""

    data_dir: Path = Path("./data")
    environment: Literal["development", "production"] = "production"
    dev_mode: bool = False
    # Host the Mini App HTTP server binds to; dev mode is only allowed on loopback.
    web_host: str = "127.0.0.1"
    web_port: int = 8080

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v

    @model_validator(mode="after")
    def _safety(self) -> Settings:
        check_dev_mode(self)
        return self

    @property
    def db_path(self) -> Path:
        return self.data_dir / "exabyte.sqlite3"

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def check_dev_mode(s: Settings) -> None:
    """DEV_MODE serves a fake user without Telegram auth: it must never reach production."""
    if not s.dev_mode:
        return
    if s.environment == "production":
        raise ConfigError("DEV_MODE=true is forbidden when ENVIRONMENT=production. Refusing to start.")
    if s.web_host not in LOOPBACK:
        raise ConfigError("DEV_MODE=true requires WEB_HOST to be localhost. Refusing to start.")


def require_runtime_secrets(s: Settings) -> None:
    """Called by main() before talking to real services (not in tests)."""
    missing = [
        name
        for name, val in (
            ("BOT_TOKEN", s.bot_token),
            ("PANEL_BASE_URL", s.panel_base_url),
            ("PANEL_USER", s.panel_user),
            ("PANEL_PASS", s.panel_pass),
        )
        if not val.get_secret_value() or "<" in val.get_secret_value()
    ]
    if missing:
        raise ConfigError(f"Missing values in .env: {', '.join(missing)}")
