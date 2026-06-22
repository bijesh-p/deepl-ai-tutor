"""Mermaid diagram renderer with a client-side error fallback.

`streamlit-mermaid` gives Python no way to detect a mermaid.js parse/render
failure — it happens inside the component's iframe, in the browser, after
the Python call has already returned successfully. A broken diagram shows
mermaid's raw "Syntax error in text mermaid version ..." with no way for
this app to intervene.

This renders mermaid.js directly (vendored locally, no CDN/runtime download)
inside an `st.iframe()`, wrapped in a JS try/catch, so a render failure can
fall back to a bullet list in the same place instead of mermaid's error text.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_VENDOR_DIR = Path(__file__).parent / "static" / "vendor"
_MERMAID_JS = (_VENDOR_DIR / "mermaid.min.js").read_text(encoding="utf-8")
_PANZOOM_JS = (_VENDOR_DIR / "svg-pan-zoom.min.js").read_text(encoding="utf-8")

# Placeholder tokens substituted via str.replace() rather than f-string/.format()
# — the JS payload is full of literal `{`/`}`, which would have to be escaped
# everywhere with either of those approaches.
_TEMPLATE = """
<html>
<head>
<style>
  html, body { margin: 0; padding: 0; overflow: hidden; }
  #mmd-container { position: relative; width: 100%; height: @@HEIGHT@@px; }
  #mmd-svg-wrap { width: 100%; height: 100%; }
  #mmd-svg-wrap svg { width: 100%; height: 100%; }
  .mmd-fallback {
    margin: 0; padding: 12px 18px; font-size: 14px; line-height: 1.6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .mmd-controls {
    position: absolute; top: 6px; right: 6px; display: flex; gap: 4px; z-index: 10;
  }
  .mmd-controls button {
    width: 26px; height: 26px; border: none; border-radius: 6px; cursor: pointer;
    background: #e5e7eb; font-size: 14px; line-height: 1;
  }
  .mmd-controls button:hover { background: #d1d5db; }
</style>
</head>
<body>
<div id="mmd-container">
  <div id="mmd-svg-wrap"></div>
  @@CONTROLS_HTML@@
</div>
<script>@@MERMAID_JS@@</script>
<script>@@PANZOOM_JS@@</script>
<script>
(function () {
  var code = @@CODE_JSON@@;
  var fallbackHtml = @@FALLBACK_HTML_JSON@@;
  var panZoomEnabled = @@PAN_ZOOM_ENABLED@@;
  var wrap = document.getElementById('mmd-svg-wrap');

  function showFallback(err) {
    if (err) { console.log('mermaid render failed, showing fallback:', err); }
    wrap.innerHTML = fallbackHtml;
  }

  try {
    mermaid.initialize({ startOnLoad: false });
    mermaid.render('mmd-graph', code).then(function (result) {
      wrap.innerHTML = result.svg;
      var svgEl = wrap.querySelector('svg');
      if (svgEl && panZoomEnabled && window.svgPanZoom) {
        window.__mmdPanZoom = window.svgPanZoom(svgEl, {
          zoomEnabled: true,
          panEnabled: true,
          controlIconsEnabled: false,
          fit: true,
          center: true,
          minZoom: 0.5,
          maxZoom: 10
        });
      }
    }).catch(showFallback);
  } catch (err) {
    showFallback(err);
  }

  document.querySelectorAll('.mmd-controls [data-action]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!window.__mmdPanZoom) { return; }
      var action = btn.getAttribute('data-action');
      if (action === 'zoom-in') { window.__mmdPanZoom.zoomIn(); }
      else if (action === 'zoom-out') { window.__mmdPanZoom.zoomOut(); }
      else if (action === 'reset') { window.__mmdPanZoom.reset(); }
    });
  });
})();
</script>
</body>
</html>
"""

_CONTROLS_HTML = (
    '<div class="mmd-controls">'
    '<button data-action="zoom-in" title="Zoom in">+</button>'
    '<button data-action="zoom-out" title="Zoom out">−</button>'
    '<button data-action="reset" title="Reset view">↻</button>'
    "</div>"
)

_NO_FALLBACK_MD = '<p class="mmd-fallback">Diagram unavailable for this topic.</p>'


def render_mermaid(
    code: str,
    fallback_bullets: list[str] | None = None,
    *,
    height: int = 350,
    pan: bool = True,
    zoom: bool = True,
    show_controls: bool = True,
) -> None:
    """Render sanitized mermaid `code`; fall back to bullets if it fails to render.

    `code` should already be sanitized (e.g. via `_sanitize_mermaid`) before
    being passed in — this function does not sanitize, only renders/falls back.
    """
    bullets = fallback_bullets or []
    if bullets:
        items = "".join(f"<li>{_escape(b)}</li>" for b in bullets)
        fallback_html = f'<ul class="mmd-fallback">{items}</ul>'
    else:
        fallback_html = _NO_FALLBACK_MD

    pan_zoom_enabled = pan or zoom
    controls_html = _CONTROLS_HTML if (show_controls and pan_zoom_enabled) else ""

    page = (
        _TEMPLATE.replace("@@HEIGHT@@", str(height))
        .replace("@@MERMAID_JS@@", _MERMAID_JS)
        .replace("@@PANZOOM_JS@@", _PANZOOM_JS)
        .replace("@@CODE_JSON@@", _js_string(code))
        .replace("@@FALLBACK_HTML_JSON@@", _js_string(fallback_html))
        .replace("@@PAN_ZOOM_ENABLED@@", "true" if pan_zoom_enabled else "false")
        .replace("@@CONTROLS_HTML@@", controls_html)
    )
    st.iframe(page, height=height)


def _js_string(text: str) -> str:
    """JSON-encode for embedding inside an inline <script> tag.

    json.dumps doesn't escape "</", so a diagram/bullet containing the
    literal text "</script>" would otherwise close our script tag early.
    """
    return json.dumps(text).replace("</", "<\\/")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
