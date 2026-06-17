from __future__ import annotations

from pathlib import Path

from user_explorer.pipeline import PipelineOptions, run
from user_explorer.viewer.render import render

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_writes_html(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "User Explorer" in html


def test_render_embeds_user_ids(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    for uid in ("101", "102", "103"):
        assert uid in html


def test_render_sentinels_replaced(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    assert "/*__USERLENS_DATA__*/" not in html
    assert "/*__USERLENS_META__*/" not in html


def test_render_embeds_event_names(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    assert "page_viewed" in html
    assert "checkout_completed" in html


def test_render_embeds_families(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    assert '"view"' in html or "'view'" in html


def test_render_with_attrs(tmp_path: Path) -> None:
    result = run(PipelineOptions(events_path=FIXTURES / "with_attrs.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    assert "user_country" in html
    assert "PL" in html
    assert "UA" in html


def test_render_heatmap_highlight_filter_present(tmp_path: Path) -> None:
    """Clicking an event chip must filter the heatmap to events of that name.

    Regression guard for a real bug: the heatmap-cell counting loop must
    short-circuit when ``highlightEvent`` is set and the current event name
    doesn't match. Without this line, the chip 'solo' state has no visible
    effect on the heatmap and all events still contribute to cell totals.
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    # The filter line short-circuits the per-event counting inside renderHeatmap.
    assert "highlightEvent && name!==highlightEvent" in html, (
        "renderHeatmap must filter events to the highlighted one when a chip is solo'd"
    )
    # Chip click handler must toggle highlightEvent.
    assert "highlightEvent = highlightEvent===n ? null : n" in html, (
        "Event-chip click must toggle highlightEvent so the heatmap re-renders filtered"
    )
    # Timeline rows must receive .hl-ev class on the highlighted event for visual cohesion.
    assert "hl-ev" in html, "Timeline event rows must support a highlight CSS class"


def test_render_flow_pathfinder_structure(tmp_path: Path) -> None:
    """Flow tab must use the Pathfinder (transition-based) explorer, not path signatures.

    Regression guard: the old implementation grouped sessions by head+tail
    signature. The new implementation builds a transition map (A→B counts)
    and renders a stepwise next-event explorer with a behavioral summary strip.
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    # Pathfinder explorer hallmarks
    assert "fp-explorer" in html, "Flow must render the Pathfinder explorer"
    assert "fp-summary" in html, "Flow must include behavioral summary strip"
    assert "Entry events" in html, "Summary strip must show entry events"
    assert "Top transition" in html, "Summary strip must show top transition"
    assert "Path diversity" in html, "Summary strip must show path diversity score"
    assert "renderFlow" in html, "renderFlow function must be present"
    # Old path-signature strings must not appear
    assert "signatureOf" not in html, "Old signature-based approach must be removed"
    assert "distinct path" not in html, "Old 'distinct paths' header must be removed"


def test_render_overview_tab_and_features(tmp_path: Path) -> None:
    """Overview tab replaces 'Top events' as the default landing tab.

    Guards: tab is renamed/reordered (Overview first, Timeline last), the
    composition bar + cohort indexing render, the Overview is wired to the
    cross-tab highlight, and the old 'Top events'/renderTopEvents are gone.
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    # Tab rename + default landing tab is Overview (pane-ev gets the 'on' class)
    assert '<button class="tab on" data-pane="pane-ev">Overview</button>' in html
    assert 'switchTab(\'pane-ev\')' in html, "selectUser must default to the Overview tab"
    # Enriched Overview hallmarks
    assert "renderOverview" in html, "renderOverview function must be present"
    assert "Activity composition" in html, "Overview must show the composition bar"
    assert "cohortShares" in html, "Overview must compute a cohort baseline"
    assert "vs avg user" in html, "Overview must show the cohort-index column"
    assert "ov-row" in html, "Overview rows must be clickable for cross-tab solo"
    # Old naming must be gone
    assert "renderTopEvents" not in html, "renderTopEvents must be renamed to renderOverview"


def test_render_inlines_logic_module(tmp_path: Path) -> None:
    """The shared analytics module must be inlined so output stays one file.

    Guards Track C2: render.py substitutes logic.js for the logic sentinel, and
    the viewer calls the shared ULLogic functions instead of inlining the math.
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    assert "/*__USERLENS_LOGIC__*/" not in html, "logic sentinel must be replaced"
    assert "var ULLogic" in html, "logic.js must be inlined into the report"
    # Render code delegates to the shared module
    assert "ULLogic.buildTransitions" in html
    assert "ULLogic.cohortIndex" in html
    assert "ULLogic.durationStats" in html


def test_render_signals_strip_surfaces_insights(tmp_path: Path) -> None:
    """The user card must render the computed-insight Signals strip.

    Guards Track B: per-user insights are embedded (blob ``ins``) and the viewer
    renders them (activity rank, engagement, adoption journey) instead of
    discarding the richest analytical content the way the old report did.
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    # Every blob carries the embedded compact insights
    assert all("ins" in b and "engagement" in b["ins"] for b in result.blobs)

    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)
    html = out.read_text(encoding="utf-8")

    assert "renderSignals" in html, "viewer must render the Signals strip"
    assert 'id="signals"' in html, "Signals container must exist in the card"
    assert "Signals · all-time" in html, "Signals strip must be labeled all-time"
    assert "Adoption journey" in html, "Signals must include the first-touch journey"
    assert "Activity rank" in html, "Signals must include the power-score rank"


def test_render_taxonomy_is_server_sourced(tmp_path: Path) -> None:
    """The viewer must consume the server taxonomy, not re-derive its own.

    Guards the dual-taxonomy collapse: the client-side ``deriveFeatures`` system
    is gone, the full ``eventFamilies`` map is embedded, and the Overview column
    reads 'Family' (not the old client-only 'Feature').
    """
    result = run(PipelineOptions(events_path=FIXTURES / "tiny.csv"))
    out = tmp_path / "out.html"
    render(result.blobs, result.meta, out, open_browser=False)

    html = out.read_text(encoding="utf-8")
    # Server taxonomy is embedded and consumed
    assert "eventFamilies" in html, "meta.eventFamilies must be embedded for client coloring"
    assert "EVENT_FAMILIES=META.eventFamilies" in html, "viewer must read families from META"
    # Client re-derivation is gone
    assert "deriveFeatures" not in html, "client-side feature derivation must be removed"
    assert "splitPrefix" not in html, "client prefix-splitting must be removed"
    # Per-family color token is injected (fixes the dead --fam-*-fg flow accent)
    assert "--fam-" in html, "per-family color custom properties must be injected"
    # Consistent naming
    assert "<th>Family</th>" in html, "Overview column must be renamed Feature -> Family"
