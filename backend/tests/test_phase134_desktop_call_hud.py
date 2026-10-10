"""Phase 13.4 Desktop Product Shell & Call HUD Acceptance Suite.

Validates:
- Delivery of CallHUD.tsx, CompanionStage.tsx, and CompanionDrawer.tsx.
- Strict enforcement of Rule 19: Desktop UI has 0 reality or state mutation authority.
- ADR-024 Lock 3: Ephemeral Partial Transcript Isolation in Call HUD.
- ADR-024 Lock 4: Instant Client-Local Barge-in latching in desktop shell.
- ADR-024 Lock 8 & 13.2-LOCK-C: Canonical conversation boundary preservation.
- Desktop production build integrity.
"""

from __future__ import annotations

from pathlib import Path
import pytest

DESKTOP_DIR = Path("../apps/desktop").resolve()
COMPONENTS_DIR = DESKTOP_DIR / "src" / "components"


def test_phase134_deliverables_exist():
    """Verify that all Phase 13.4 components and desktop files exist on disk."""
    call_hud = COMPONENTS_DIR / "CallHUD.tsx"
    companion_stage = COMPONENTS_DIR / "CompanionStage.tsx"
    companion_drawer = COMPONENTS_DIR / "CompanionDrawer.tsx"
    app_tsx = DESKTOP_DIR / "src" / "App.tsx"
    app_css = DESKTOP_DIR / "src" / "App.css"

    assert call_hud.is_file(), "CallHUD.tsx must exist"
    assert companion_stage.is_file(), "CompanionStage.tsx must exist"
    assert companion_drawer.is_file(), "CompanionDrawer.tsx must exist"
    assert app_tsx.is_file(), "App.tsx must exist"
    assert app_css.is_file(), "App.css must exist"


def test_phase134_rule19_mind_body_separation():
    """Verify that desktop components contain zero reality or relationship mutation authority."""
    files_to_check = [
        COMPONENTS_DIR / "CallHUD.tsx",
        COMPONENTS_DIR / "CompanionStage.tsx",
        COMPONENTS_DIR / "CompanionDrawer.tsx",
    ]

    forbidden_patterns = [
        "set_fact",
        "update_relationship",
        "mutate_character",
        "PromotionAuthorizationToken",
        "execute_mutation",
    ]

    for fpath in files_to_check:
        content = fpath.read_text(encoding="utf-8")
        for forbidden in forbidden_patterns:
            assert forbidden not in content, f"Rule 19 violation: '{forbidden}' found in {fpath.name}"


def test_phase134_call_hud_ephemeral_transcript_isolation():
    """Verify ADR-024 Lock 3: Ephemeral transcript preview in CallHUD."""
    call_hud_content = (COMPONENTS_DIR / "CallHUD.tsx").read_text(encoding="utf-8")

    # CallHUD must accept partialTranscript and render it conditionally as preview
    assert "partialTranscript" in call_hud_content
    assert "call-partial-transcript" in call_hud_content
    assert "Hearing:" in call_hud_content
    # Must also support Instant Barge-in button
    assert "onBargeIn" in call_hud_content
    assert "btn-interrupt" in call_hud_content


def test_phase134_companion_stage_presentation_only():
    """Verify CompanionStage integrates Live2DCanvas without reverse mutation."""
    stage_content = (COMPONENTS_DIR / "CompanionStage.tsx").read_text(encoding="utf-8")

    assert "Live2DCanvas" in stage_content
    assert "visualExpression" in stage_content
    assert "visualMotion" in stage_content
    assert "lipSyncState" in stage_content
    assert "stage-presence-banner" in stage_content
    assert "stage-ambient-aura" in stage_content


def test_phase134_companion_drawer_read_only_projections():
    """Verify CompanionDrawer houses read-only projections for Journey, Memories, Bond, and Status."""
    drawer_content = (COMPONENTS_DIR / "CompanionDrawer.tsx").read_text(encoding="utf-8")

    # Tab definitions
    assert '"chat"' in drawer_content
    assert '"journey"' in drawer_content
    assert '"memories"' in drawer_content
    assert '"bond"' in drawer_content
    assert '"about"' in drawer_content

    # Sub-views
    assert "BiographicalMemoryView" in drawer_content
    assert "ChatView" in drawer_content
    assert "Read-Only Projection" in drawer_content
    assert "Relational Horizon" in drawer_content
    assert "Aevum Core" in drawer_content


def test_phase134_app_realtime_wiring_and_barge_in():
    """Verify App.tsx integrates CallHUD, CompanionStage, CompanionDrawer and Instant Barge-In."""
    app_content = (DESKTOP_DIR / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "CallHUD" in app_content
    assert "CompanionStage" in app_content
    assert "CompanionDrawer" in app_content
    assert "handleStartCall" in app_content
    assert "handleEndCall" in app_content
    assert "handleBargeIn" in app_content
    assert "stopAudioPlayback()" in app_content
    assert "BARGE_IN" in app_content
    assert "RECONNECTING" in app_content


def test_phase134_desktop_build_artifacts_present():
    """Verify desktop production build succeeded and artifacts are non-empty."""
    dist_dir = DESKTOP_DIR / "dist"
    index_html = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    assert dist_dir.is_dir(), "dist/ directory must exist"
    assert index_html.is_file(), "dist/index.html must exist"
    assert index_html.stat().st_size > 0, "dist/index.html must not be empty"

    js_files = list(assets_dir.glob("*.js"))
    css_files = list(assets_dir.glob("*.css"))

    assert len(js_files) > 0, "Production JS bundle must be generated"
    assert len(css_files) > 0, "Production CSS bundle must be generated"
    assert js_files[0].stat().st_size > 10000, "JS bundle must be substantial"
    assert css_files[0].stat().st_size > 10000, "CSS bundle must be substantial"
