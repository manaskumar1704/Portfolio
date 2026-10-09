"""Typed settings, read from the environment once at startup.

Everything the app needs from outside itself arrives here. Nothing else in
`app/` reads `os.environ`, so there is exactly one place to look when a
variable is missing, and a missing variable crashes at boot instead of failing
on the first request that happens to need it.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# pydantic-settings JSON-decodes any complex field before validators run, so a
# plain `list[str]` field would demand `["a","b"]` in the environment and reject
# the CSV a human actually writes. NoDecode hands the raw string to the
# validator below instead.
CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"
    cors_origins: CsvList = Field(default_factory=list)

    # Phase 2. The pooled URL is what the app uses; Alembic wants sync
    # separately because it runs its own blocking engine.
    database_url: str = ""
    sync_database_url: str = ""

    # Phase 3. Gemini primary: gemini-3.5-flash-lite is the cheapest no-card
    # option that does function calling properly, and the demo is a streaming
    # UI where time-to-first-token is the product. Groq is the 429 fallback.
    llm_provider: str = "gemini"

    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str = ""

    groq_model: str = "openai/gpt-oss-120b"
    groq_api_key: str = ""

    # Phase 4. 384 dimensions, which is what the vector column is declared as.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    # Phase 5.
    github_token: str = ""
    github_pins: CsvList = Field(default_factory=list)
    resend_api_key: str = ""
    contact_notify_email: str = ""

    # Phase 6.
    rate_limit_per_minute: int = 10
    rate_limit_burst: int = 10
    approve_limit_per_hour: int = 3

    # Phase 7.
    mcp_auth_token: str = ""

    # Phase 8. All three empty means tracing is a no-op, so local runs and CI
    # need no Langfuse account.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("cors_origins", "github_pins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        """Accept `a,b` from the environment; leave real lists alone for tests."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def llm_api_key(self) -> str:
        """The key for the configured provider, or empty when it is missing.

        `build_llm_client` uses this to fail at startup with a message that
        names the variable, instead of at the first visitor's request with a
        401 from a provider SDK.
        """
        if self.llm_provider.lower() == "gemini":
            return self.gemini_api_key
        return self.groq_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
