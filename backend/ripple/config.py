"""Runtime configuration loaded from environment / .env."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "ripple"

    robot_adapter: Literal["mock", "cyberwave"] = "mock"
    cyberwave_api_key: str | None = None

    cyberwave_workspace_id: str | None = None
    cyberwave_environment_id: str | None = None
    cyberwave_twin_id: str | None = None

    llm_api_key: str | None = None
    llm_model: str = "claude-sonnet-5-5"


def get_settings() -> Settings:
    return Settings()
