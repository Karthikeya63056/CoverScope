"""Environment-backed configuration for CoverScope."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv

from backend.qa.reliability import parse_page_selection

load_dotenv()

# Measured against three public Indian health policy wordings:
# 20,703 / 110,757 / 188,927 extracted characters. 250k leaves headroom
# without approaching a typical model's practical prompt budget.
DEFAULT_MAX_EXTRACTED_CHARS = 250_000
DEFAULT_MAX_UPLOAD_BYTES = 20_000_000
DEFAULT_CHUNK_CHARS = 1_800
DEFAULT_MIN_PAGE_CHARS = 40
DEFAULT_RETRIEVAL_TOP_K = 5
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_TIMEOUT_SECONDS = 30.0

DEFAULT_GROQ_MAX_COMPLETION_TOKENS = 2_500


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _non_empty(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class Settings:
    max_extracted_chars: int = _positive_int(
        "COVERSCOPE_MAX_EXTRACTED_CHARS", DEFAULT_MAX_EXTRACTED_CHARS
    )
    # A cheap guard before reading bytes. The extracted-character limit below
    # remains the authoritative content limit; neither value truncates input.
    max_upload_bytes: int = _positive_int(
        "COVERSCOPE_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES
    )
    chunk_chars: int = _positive_int("COVERSCOPE_CHUNK_CHARS", DEFAULT_CHUNK_CHARS)
    min_page_chars: int = _positive_int(
        "COVERSCOPE_MIN_PAGE_CHARS", DEFAULT_MIN_PAGE_CHARS
    )
    retrieval_top_k: int = _positive_int(
        "COVERSCOPE_RETRIEVAL_TOP_K", DEFAULT_RETRIEVAL_TOP_K
    )
    groq_model: str = _non_empty("COVERSCOPE_GROQ_MODEL", DEFAULT_GROQ_MODEL)
    groq_timeout_seconds: float = _positive_float(
        "COVERSCOPE_GROQ_TIMEOUT_SECONDS", DEFAULT_GROQ_TIMEOUT_SECONDS
    )
    groq_max_completion_tokens: int = _positive_int(
        "COVERSCOPE_GROQ_MAX_COMPLETION_TOKENS",
        DEFAULT_GROQ_MAX_COMPLETION_TOKENS,
    )
    # Explicit manual-review flags. This is intentionally separate from the
    # noisy heuristic table-review flags in quality_checks.
    unreliable_pages: tuple[int, ...] = parse_page_selection(
        os.getenv("COVERSCOPE_UNRELIABLE_PAGES")
    )
    # MongoDB Atlas configuration (optional; falls back to in-memory session mode when unset)
    mongodb_uri: str | None = os.getenv("MONGODB_URI")
    mongodb_database: str = _non_empty("MONGODB_DATABASE", "coverscope")
    mongodb_server_selection_timeout_ms: int = _positive_int(
        "COVERSCOPE_MONGODB_TIMEOUT_MS", 2500
    )
    mongodb_connect_timeout_ms: int = _positive_int(
        "COVERSCOPE_MONGODB_CONNECT_TIMEOUT_MS", 2500
    )


settings = Settings()
