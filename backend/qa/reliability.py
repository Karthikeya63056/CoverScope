"""Explicit page-level reliability flags.

The extraction heuristic in quality_checks deliberately over-flags tables.
Only pages listed by the operator (COVERSCOPE_UNRELIABLE_PAGES) are treated as
known-unreliable for answer validation.
"""
from __future__ import annotations

import re

_PART_SEPARATOR = re.compile(r"[\s,]+")
_RANGE = re.compile(r"^(\d+)-(\d+)$")
_ENV_NAME = "COVERSCOPE_UNRELIABLE_PAGES"


def parse_page_selection(value: str | None) -> tuple[int, ...]:
    """Parse values such as "50, 51-52" into a sorted tuple of page numbers."""
    if value is None or not value.strip():
        return ()

    pages: set[int] = set()
    for part in _PART_SEPARATOR.split(value.strip()):
        if not part:
            continue
        match = _RANGE.fullmatch(part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start <= 0 or end <= 0:
                raise ValueError(
                    f"{_ENV_NAME} page numbers must be greater than zero"
                )
            if end < start:
                raise ValueError(
                    f"{_ENV_NAME} range {part!r} ends before it starts"
                )
            pages.update(range(start, end + 1))
            continue
        if not part.isdigit():
            raise ValueError(
                f"{_ENV_NAME} contains invalid entry {part!r}; "
                "use page numbers or ranges such as 50,51-52"
            )
        page = int(part)
        if page <= 0:
            raise ValueError(f"{_ENV_NAME} page numbers must be greater than zero")
        pages.add(page)
    return tuple(sorted(pages))


def is_explicitly_unreliable(page_number: int, flagged: tuple[int, ...]) -> bool:
    return page_number in flagged
