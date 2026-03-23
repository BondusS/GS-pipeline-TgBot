from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    admins: Annotated[list[int], NoDecode] = Field(default_factory=list, alias="ADMINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admins", mode="before")
    @classmethod
    def parse_admins(cls, v: Any) -> list[int]:
        if v is None or v == "":
            return []

        if isinstance(v, int):
            return [v]

        if isinstance(v, list):
            result: list[int] = []
            for item in v:
                if str(item).strip():
                    result.append(int(item))
            return result

        if isinstance(v, str):
            parts = [part.strip() for part in v.split(",") if part.strip()]
            return [int(part) for part in parts]

        raise ValueError("ADMINS must be a comma-separated string or list of ints")


settings = Settings()
