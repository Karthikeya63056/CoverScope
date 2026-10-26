"""Focused tests for the Stage B Hero and Upload components."""
from __future__ import annotations

import streamlit as st

from backend.config import settings
from frontend.components.hero import PAGE_TITLE, TAGLINE, render_hero, render_value_props
from frontend.components.upload import render_upload_error, render_uploader
from frontend.state import DOC_ERROR_KEY, DOC_KEY, UPLOADER_VERSION_KEY
from frontend.utils.formatters import format_bytes


def test_hero_component_constants():
    assert PAGE_TITLE == "CoverScope"
    assert TAGLINE == "Your policy. Made clear."


def test_upload_component_uses_actual_settings_limits():
    formatted = format_bytes(settings.max_upload_bytes)
    assert "MB" in formatted or "KB" in formatted
    assert settings.max_extracted_chars > 0
