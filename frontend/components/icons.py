"""Reusable inline SVG icon helpers for the CoverScope interface.

Provides accessible, resolution-independent vector icons without requiring
external icon dependencies or relying primarily on emoji.
"""
from __future__ import annotations


def svg_icon(
    svg_body: str,
    *,
    size: int = 16,
    color: str = "currentColor",
    extra_class: str = "",
) -> str:
    """Wrap raw SVG paths in a styled SVG tag."""
    cls_attr = f' class="cs-icon {extra_class}"' if extra_class else ' class="cs-icon"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"{cls_attr} '
        f'style="vertical-align: -0.18em; display: inline-block;">'
        f"{svg_body}</svg>"
    )


def icon_brand_symbol(size: int = 26, color: str = "#0f766e") -> str:
    """Custom CoverScope emblem combining a security shield with an evidence document fold."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 32 32" fill="none" class="cs-brand-emblem" style="display:inline-block; vertical-align:middle;">'
        f'<rect width="32" height="32" rx="8" fill="#0a2233"/>'
        f'<path d="M16 6L8 9.5V16C8 21.2 11.4 25.8 16 27C20.6 25.8 24 21.2 24 16V9.5L16 6Z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M12.5 15.5L15 18L19.5 13.5" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def icon_shield(size: int = 18, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        size=size,
        color=color,
    )


def icon_file_text(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/>'
        '<polyline points="10 9 9 9 8 9"/>',
        size=size,
        color=color,
    )


def icon_check_circle(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>',
        size=size,
        color=color,
    )


def icon_x_circle(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>',
        size=size,
        color=color,
    )


def icon_alert_triangle(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>',
        size=size,
        color=color,
    )


def icon_help_circle(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>',
        size=size,
        color=color,
    )


def icon_lock(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        size=size,
        color=color,
    )


def icon_search(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<circle cx="11" cy="11" r="8"/>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65"/>',
        size=size,
        color=color,
    )


def icon_bookmark(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
        size=size,
        color=color,
    )


def icon_info(size: int = 16, color: str = "currentColor") -> str:
    return svg_icon(
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="16" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12.01" y2="8"/>',
        size=size,
        color=color,
    )


def icon_upload(size: int = 18, color: str = "currentColor") -> str:
    return svg_icon(
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>',
        size=size,
        color=color,
    )
