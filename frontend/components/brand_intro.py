"""Brand intro and premium loading experience component for CoverScope."""
from __future__ import annotations

import base64
import functools
from pathlib import Path

import streamlit as st

from frontend.components.icons import icon_brand_symbol, icon_shield
from frontend.utils.formatters import clean_html

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."
HEADLINE = "Clarity in every clause."
SUBTITLE = "Making health insurance easier to understand."
TRUST_LINE = "Evidence-led answers · Transparent limitations"


@functools.lru_cache(maxsize=1)
def _load_cinematic_assets() -> tuple[str, str]:
    """Load and base64-encode the photorealistic 3D rendered assets once."""
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    p1 = assets_dir / "scene1_document_scan.jpg"
    p2 = assets_dir / "scene3_glass_shield.jpg"
    b64_1 = base64.b64encode(p1.read_bytes()).decode("utf-8") if p1.exists() else ""
    b64_2 = base64.b64encode(p2.read_bytes()).decode("utf-8") if p2.exists() else ""
    return b64_1, b64_2


def render_cinematic_intro(force_play: bool = False) -> None:
    """Render the cinematic 3D loading and brand intro overlay.

    Features:
    - Scene 1: Floating physical Indian health insurance policy document in 3D studio
      space with volumetric teal rim lighting and contact shadows.
    - Scene 2: High-intensity cyan laser scanning sweep traversing policy clauses with
      active text illumination and floating 3D telemetry particle motes.
    - Scene 3: Convergence into a 3D translucent glass shield emblem with realistic caustics,
      refraction, depth, and edge reflections, followed by brand typography reveal.
    - Scene 4: Smooth transition and dissolve directly into the CoverScope application.
    - Accessible: Skips immediately on prefers-reduced-motion, provides Skip button [Esc],
      and plays once per session unless replayed on demand.
    """
    b64_doc, b64_shield = _load_cinematic_assets()
    if not b64_doc or not b64_shield:
        return

    # Check if intro was already played in Streamlit session state
    if not force_play and st.session_state.get("cs_intro_played", False):
        return

    st.session_state["cs_intro_played"] = True

    # Generate floating particle motes with randomized positions and delays
    particles_html = "".join(
        f'<div class="cs-intro-particle" style="left:{15 + (i * 7) % 70}%; bottom:{25 + (i * 5) % 35}%; width:{3 + (i % 4)}px; height:{3 + (i % 4)}px; animation-delay:{0.8 + (i * 0.12):.2f}s;"></div>'
        for i in range(16)
    )

    intro_html = f"""
    <div id="cs-cinematic-intro" role="dialog" aria-label="CoverScope Introduction">
      <!-- Skip intro button -->
      <button class="cs-intro-skip-btn" onclick="const el=document.getElementById('cs-cinematic-intro'); if(el){{ el.style.opacity='0'; el.style.pointerEvents='none'; setTimeout(()=>el.style.display='none', 250); }}" aria-label="Skip introduction">
        <span>Skip Intro</span>
        <kbd>Esc</kbd>
      </button>

      <!-- Keyboard escape listener helper -->
      <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
           onload="window.addEventListener('keydown', (e) => {{ if (e.key === 'Escape') {{ const el = document.getElementById('cs-cinematic-intro'); if (el) {{ el.style.opacity='0'; el.style.pointerEvents='none'; setTimeout(() => el.style.display='none', 250); }} }} }}, {{once: true}});"
           style="display:none;" alt="" />

      <div class="cs-intro-viewport">
        <div class="cs-intro-ambient-glow"></div>

        <!-- Scene 1 & 2: 3D Policy Document & Scanning Layer -->
        <div class="cs-scene-doc-layer">
          <img class="cs-scene-img" src="data:image/jpeg;base64,{b64_doc}" alt="Insurance policy document scan" />
          <div class="cs-scene-scanline"></div>

          <div class="cs-scene-clause-hud">
            <span class="cs-clause-hud-pulse"></span>
            <div>
              <div class="cs-clause-hud-text">Scanning Policy Clauses</div>
              <div class="cs-clause-hud-subtext">Section 4.1 &middot; Pre-Existing Disease Exclusion &middot; 36 Months</div>
            </div>
          </div>

          <div class="cs-intro-particles-container">
            {particles_html}
          </div>
        </div>

        <!-- Scene 3: 3D Glass Shield Emblem Layer -->
        <div class="cs-scene-shield-layer">
          <img class="cs-scene-img" src="data:image/jpeg;base64,{b64_shield}" alt="CoverScope 3D glass shield emblem" />
        </div>

        <!-- Scene 3 Ending Brand Plate: Razor-sharp crystal-clear typography -->
        <div class="cs-scene-shield-brandbox">
          <div class="cs-brandbox-plate">
            <div class="cs-brandbox-badge">Verified Policy Intelligence</div>
            <div class="cs-brandbox-title">{PAGE_TITLE}</div>
            <div class="cs-brandbox-tagline">{TAGLINE}</div>
          </div>
        </div>
      </div>
    </div>
    """
    st.markdown(clean_html(intro_html), unsafe_allow_html=True)




def render_brand_intro(compact: bool = False) -> None:
    """Render the cinematic brand intro and loading card.

    Features:
    - Deep navy-to-dark-teal gradient surface (#071D2B to #0A2233)
    - Subtle radial mint ambient glow and geometric grid
    - Brand emblem with mint halo (#5EEAD4)
    - Animated shimmer progress line (non-blocking)
    - Accessible: supports prefers-reduced-motion

    Parameters
    ----------
    compact : bool
        If True, renders a streamlined version for compact views.
    """
    emblem = icon_brand_symbol(size=38, color="#5eead4")

    if compact:
        html = f"""
        <div class="cs-brand-intro-card cs-brand-intro-compact">
          <div style="display:flex; align-items:center; gap:0.65rem;">
            {emblem}
            <div>
              <div style="font-size:1.15rem; font-weight:800; color:#ffffff; letter-spacing:-0.02em;">{PAGE_TITLE}</div>
              <div style="font-size:0.8rem; color:#5eead4; font-weight:600;">{TAGLINE}</div>
            </div>
          </div>
        </div>
        """
        st.markdown(clean_html(html), unsafe_allow_html=True)
        return

    html = f"""
    <div class="cs-brand-intro-wrapper">
      <div class="cs-brand-intro-card">
        <div class="cs-intro-glow"></div>
        <div class="cs-intro-center-cluster">
          <div class="cs-intro-emblem-badge">
            {emblem}
          </div>
          <div class="cs-intro-brand-title">{PAGE_TITLE}</div>
          <div class="cs-intro-tagline">{TAGLINE}</div>
          <h2 class="cs-intro-headline">{HEADLINE}</h2>
          <p class="cs-intro-subtitle">{SUBTITLE}</p>
          <div class="cs-intro-shimmer-track">
            <div class="cs-intro-shimmer-bar"></div>
          </div>
          <div class="cs-intro-trust-line">
            <span class="cs-intro-trust-dot"></span>
            <span>{TRUST_LINE}</span>
            <span class="cs-intro-trust-dot"></span>
          </div>
        </div>
      </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def render_real_time_status(stage_title: str, stage_description: str) -> None:
    """Render an honest, un-fabricated status card for active background execution.

    Parameters
    ----------
    stage_title : str
        The active operational step (e.g., 'Reading your policy document').
    stage_description : str
        Factual description of what the backend is performing.
    """
    html = f"""
    <div class="cs-active-operation-card">
      <div class="cs-active-pulse-orb"></div>
      <div>
        <div class="cs-active-op-title">{stage_title}</div>
        <div class="cs-active-op-subtext">{stage_description}</div>
      </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)
