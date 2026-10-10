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
    # Changing the model means re-running the ingest: rows written by two models
    # have no meaningful distance between them, and `ingest_runs` records which
    # one wrote which batch.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    # Where the markdown lives. A path, so the real corpus can move to its own
    # repository without a code change.
    corpus_dir: str = "corpus"
    # PDFs go here and stay gitignored. ingest/from_pdf.py reads it.
    corpus_source_dir: str = "corpus/_source"

    # Phase 5. The GitHub tool is restricted to repos under `github_owner`, which
    # is what stops a visitor pointing it at arbitrary URLs and burning the
    # token's rate limit. `github_pins` is what the tool returns when the model
    # asks for no particular repo.
    #
    # A fine-grained PAT with `public_repo` read access. Fine-grained rather than
    # classic because the classic token's scope is account-wide; fine-grained
    # means a leaked token cannot read anything this project does not already
    # publish. See .env.example.
    github_token: str = ""
    github_owner: str = ""
    github_pins: CsvList = Field(default_factory=list)
    # Seconds a repo response stays fresh. Star counts do not change by the
    # minute, and a recruiter asking twice should not cost two API calls.
    github_cache_ttl: int = 900
    github_timeout_seconds: float = 8.0
    # Phase 6. The visitor's IP is personal data, so only a salted hash of it is
    # stored — and the hash is nulled the moment a message is sent.
    #
    # `ip_hash_salt` must be a long random string. Losing it means existing
    # hashes can no longer be matched against an incoming request, so every
    # outstanding draft becomes unapprovable. That is the intended failure mode:
    # drafts are abandoned, never sent by someone else.
    ip_hash_salt: str = ""

    # Peers allowed to set X-Forwarded-For. Empty means "trust nobody", which is
    # the correct default: with an empty list the IP check degrades to the socket
    # peer and cannot be spoofed, at the cost of breaking approval for everyone
    # behind a proxy. Populated after observing the real headers via
    # GET /_probe/headers — see ADR 0006.
    trusted_proxy_cidrs: CsvList = Field(default_factory=list)

    # Resend sender. `onboarding@resend.dev` only delivers to the account's own
    # address, so this is a working smoke test rather than a public contact
    # path. Switch to a verified domain sender when one exists; it is a setting,
    # not a code change.
    resend_api_key: str = ""
    contact_notify_email: str = ""
    resend_from: str = "onboarding@resend.dev"

    # Phase 6. Public endpoint limits.
    rate_limit_per_minute: int = 10
    rate_limit_burst: int = 10
    approve_limit_per_hour: int = 3

    # The global daily send ceiling. Resend's free tier allows 100/day; this sits
    # below it so failures, manual sends and the refund path cannot push the
    # account over.
    #
    # In the database rather than in process, because an in-process counter
    # resets on every Render spin-down: ten sends before a sleep and ten after
    # would be twenty.
    daily_send_cap: int = 70

    # Retention. Unsent drafts are deleted after this; sent rows keep only their
    # body for long enough to be noticed, and their IP hash is cleared on send.
    draft_retention_days: int = 7
    sent_row_retention_days: int = 30

    # Probability that any one request triggers the retention sweep. There is no
    # cron on this tier, so the sweep runs on boot and opportunistically here.
    retention_sweep_percent: int = 2

    # Phase 7.
    mcp_auth_token: str = ""

    # Phase 8. All three empty means tracing is a no-op, so local runs and CI
    # need no Langfuse account.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("cors_origins", "github_pins", "trusted_proxy_cidrs", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        """Accept `a,b` from the environment; leave real lists alone for tests.

        An empty string is the same as unset. `TRUSTED_PROXY_CIDRS=` in a `.env`
        file is how "trust nobody" is spelled, and it must not become `[""]`,
        which would be a malformed CIDR rather than an empty allowlist.
        """
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def ip_hashing_enabled(self) -> bool:
        """Whether visitor IPs can be hashed at all.

        Without a salt there is nothing to hash *with*, and a draft written while
        the salt was missing could never be approved afterwards. Callers refuse to
        create a draft rather than storing a hash of an unsalted address, which
        would be reversible by brute force over the whole IPv4 space.
        """
        return len(self.ip_hash_salt) >= 16

    @property
    def email_enabled(self) -> bool:
        return bool(self.resend_api_key and self.contact_notify_email)

    def require_email(self) -> None:
        """Fail at boot, naming the variable, when sending is half-configured."""
        missing = [
            name
            for name, value in (
                ("RESEND_API_KEY", self.resend_api_key),
                ("CONTACT_NOTIFY_EMAIL", self.contact_notify_email),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Email sending is enabled but not configured. Set: "
                + ", ".join(missing)
                + ". The send route refuses to report success without them, "
                "rather than silently dropping a visitor's message."
            )

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

    def allowed_github_repos(self) -> set[str]:
        """The repos `get_github_repo` will look at, lowercased.

        An allowlist rather than a blocklist because the failure mode is
        asymmetric: an over-broad list spends the token's rate limit on repos a
        visitor named, while a narrow one just fails to answer an unusual
        question. `github_owner` is the real boundary — `github_pins` narrows it
        to the repos worth demoing.
        """
        repos = set()
        for entry in self.github_pins:
            name = entry.strip().lower().strip("/")
            if not name:
                continue
            # A pin that is not `owner/repo` gets the configured owner, so
            # `Portfolio` works as well as `manas-dev/Portfolio`.
            repos.add(name if "/" in name else f"{self.github_owner.lower()}/{name}")
        return repos

    def require_github(self) -> None:
        """Fail at startup, naming the variable, when GitHub is half-configured.

        Called from the lifespan rather than at first use, so a missing token is
        a boot failure with a clear message instead of a 500 in front of the
        first recruiter who asks about a repository.
        """
        missing = [
            name
            for name, value in (
                ("GITHUB_TOKEN", self.github_token),
                ("GITHUB_OWNER", self.github_owner),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "GitHub tool is enabled but not configured. Set: "
                + ", ".join(missing)
                + ". The tool is allowlisted to GITHUB_OWNER on purpose: it stops "
                "a visitor pointing it at arbitrary repos and spending the token's "
                "rate limit."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
