"""Design system tokens for CoverScope.

Fintech / editorial direction:
- Deep navy / blue-charcoal as principal brand anchor
- Muted deep teal as modern intelligence accent
- Warm ivory and clean slate surfaces
- High-contrast, legible typography
- Restrained semantic colors for coverage verdicts
"""
from __future__ import annotations

# --- Brand & Surface Colors ---
COLOR_PRIMARY_NAVY = "#0a2233"
COLOR_PRIMARY_NAVY_DARK = "#061622"
COLOR_ACCENT_TEAL = "#0f766e"
COLOR_ACCENT_TEAL_DARK = "#0d5f58"
COLOR_ACCENT_TEAL_LIGHT = "#ccfbf1"

# Surfaces & Backgrounds
COLOR_BG_PAGE = "#f7f6f2"          # Warm ivory neutral
COLOR_SURFACE_CARD = "#ffffff"     # Clean card white
COLOR_SURFACE_HOVER = "#f1f5f9"
COLOR_BORDER_SUBTLE = "#e2e8f0"    # Crisp thin border
COLOR_BORDER_STRONG = "#cbd5e1"
COLOR_BORDER_FOCUS = "#0f766e"

# Typography Colors
COLOR_TEXT_PRIMARY = "#0f172a"    # High-contrast slate-900
COLOR_TEXT_BODY = "#334155"       # Slate-700
COLOR_TEXT_MUTED = "#64748b"      # Slate-500
COLOR_TEXT_DISABLED = "#94a3b8"   # Slate-400
COLOR_TEXT_INVERSE = "#ffffff"

# Semantic & Verdict Colors
COLOR_VERDICT_COVERED = "#15803d"       # Forest green
COLOR_VERDICT_COVERED_BG = "#f0fdf4"
COLOR_VERDICT_COVERED_BORDER = "#bbf7d0"

COLOR_VERDICT_EXCLUDED = "#b91c1c"      # Deep crimson
COLOR_VERDICT_EXCLUDED_BG = "#fef2f2"
COLOR_VERDICT_EXCLUDED_BORDER = "#fecaca"

COLOR_VERDICT_DEPENDS = "#b45309"       # Warm amber
COLOR_VERDICT_DEPENDS_BG = "#fffbeb"
COLOR_VERDICT_DEPENDS_BORDER = "#fde68a"

COLOR_VERDICT_NOT_STATED = "#475569"    # Slate
COLOR_VERDICT_NOT_STATED_BG = "#f8fafc"
COLOR_VERDICT_NOT_STATED_BORDER = "#cbd5e1"

COLOR_STATUS_WARNING = "#b45309"
COLOR_STATUS_WARNING_BG = "#fffbeb"
COLOR_STATUS_WARNING_BORDER = "#fcd34d"

COLOR_STATUS_INFO = "#0369a1"
COLOR_STATUS_INFO_BG = "#f0f9ff"
COLOR_STATUS_INFO_BORDER = "#bae6fd"

# Typography Scale
FONT_FAMILY = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", '
    'Arial, sans-serif'
)
FONT_SIZE_2XS = "0.72rem"
FONT_SIZE_XS = "0.78rem"
FONT_SIZE_SM = "0.875rem"
FONT_SIZE_BASE = "1rem"
FONT_SIZE_LG = "1.125rem"
FONT_SIZE_XL = "1.35rem"
FONT_SIZE_2XL = "1.75rem"
FONT_SIZE_3XL = "2.25rem"
FONT_SIZE_4XL = "3.25rem"

FONT_WEIGHT_NORMAL = "400"
FONT_WEIGHT_MEDIUM = "500"
FONT_WEIGHT_SEMIBOLD = "600"
FONT_WEIGHT_BOLD = "700"
FONT_WEIGHT_EXTRABOLD = "800"

# Spacing Scale
SPACE_1 = "0.25rem"
SPACE_2 = "0.5rem"
SPACE_3 = "0.75rem"
SPACE_4 = "1rem"
SPACE_5 = "1.25rem"
SPACE_6 = "1.5rem"
SPACE_8 = "2rem"
SPACE_10 = "2.5rem"
SPACE_12 = "3rem"

# Border Radii
RADIUS_SM = "6px"
RADIUS_MD = "10px"
RADIUS_LG = "14px"
RADIUS_XL = "20px"
RADIUS_FULL = "9999px"

# Elevation / Box Shadows
SHADOW_SM = "0 1px 2px 0 rgba(15, 23, 42, 0.05)"
SHADOW_MD = "0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05)"
SHADOW_LG = "0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)"

# Layout
MAX_CONTENT_WIDTH = "1080px"
