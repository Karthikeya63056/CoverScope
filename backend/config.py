"""Environment-backed configuration for CoverScope."""
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


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


@dataclass(frozen=True)
class Settings:
    # Provisional until measured against 2–3 sample policy PDFs and the chosen model.
    max_extracted_chars: int = _positive_int(
        "COVERSCOPE_MAX_EXTRACTED_CHARS", 400_000
    )
    chunk_chars: int = _positive_int("COVERSCOPE_CHUNK_CHARS", 1_800)
    min_page_chars: int = _positive_int("COVERSCOPE_MIN_PAGE_CHARS", 40)


settings = Settings()
