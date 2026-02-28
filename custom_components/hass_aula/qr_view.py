"""QR code view for MitID authentication in the Aula integration."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import LOGGER


def generate_animated_qr_svg(qr1: Any, qr2: Any) -> str:
    """
    Generate an animated SVG that alternates between two QR codes.

    The MitID app expects two QR codes to be scanned alternately.
    This function creates a single SVG with CSS animation that toggles
    between the two QR codes every 2 seconds.
    """
    matrix1 = qr1.get_matrix()
    matrix2 = qr2.get_matrix()

    size1 = len(matrix1)
    size2 = len(matrix2)
    size = max(size1, size2)

    # Add quiet zone
    module_size = 4
    quiet_zone = 4
    svg_size = (size + 2 * quiet_zone) * module_size

    modules1 = _matrix_to_rects(matrix1, module_size, quiet_zone)
    modules2 = _matrix_to_rects(matrix2, module_size, quiet_zone)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_size} {svg_size}" '
        f'width="{svg_size}" height="{svg_size}">'
        "<style>"
        ".qr1{animation:swap 4s step-end infinite}"
        ".qr2{animation:swap 4s step-end infinite;animation-delay:2s;opacity:0}"
        "@keyframes swap{0%,49%{opacity:1}50%,100%{opacity:0}}"
        "</style>"
        f'<rect width="{svg_size}" height="{svg_size}" fill="white"/>'
        f'<g class="qr1">{modules1}</g>'
        f'<g class="qr2">{modules2}</g>'
        "</svg>"
    )


def _matrix_to_rects(
    matrix: list[list[bool]],
    module_size: int,
    quiet_zone: int,
) -> str:
    """Convert a QR code matrix to SVG rect elements."""
    rects: list[str] = []
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                x = (col_idx + quiet_zone) * module_size
                y = (row_idx + quiet_zone) * module_size
                rects.append(
                    f'<rect x="{x}" y="{y}" '
                    f'width="{module_size}" height="{module_size}" fill="black"/>'
                )
    return "".join(rects)


class AulaQRView(HomeAssistantView):
    """Serve the animated QR code SVG for MitID authentication."""

    requires_auth = False
    cors_allowed = True

    def __init__(self, flow_id: str) -> None:
        """Initialize the QR view."""
        self._flow_id = flow_id
        self._svg: str | None = None
        self.url = f"/api/hass_aula/qr/{flow_id}"
        self.name = f"api:hass_aula:qr:{flow_id}"

    def update_svg(self, svg: str) -> None:
        """Update the SVG content."""
        self._svg = svg

    async def get(self, request: web.Request) -> web.Response:  # noqa: ARG002
        """Handle GET request for the QR code SVG."""
        if self._svg is None:
            LOGGER.warning("QR view GET %s — no SVG yet (returning 404)", self.url)
            return web.Response(status=404, text="QR code not yet available")

        LOGGER.debug("QR view GET %s — serving SVG (%d bytes)", self.url, len(self._svg))
        return web.Response(
            body=self._svg,
            content_type="image/svg+xml",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
