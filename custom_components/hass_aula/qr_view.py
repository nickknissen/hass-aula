"""QR code view for MitID authentication in the Aula integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    import qrcode

QR_PATH = "/api/hass_aula/qr/{flow_id}"
QR_URL_EXPIRY = timedelta(minutes=10)
DATA_QR_SVGS: HassKey[dict[str, str]] = HassKey(f"{DOMAIN}_qr_svgs")


@callback
def async_register_qr_view(hass: HomeAssistant) -> None:
    """Register the QR view on first use; every flow shares it."""
    if DATA_QR_SVGS in hass.data:
        return
    hass.data[DATA_QR_SVGS] = {}
    hass.http.register_view(AulaQRView())


@callback
def async_set_qr_svg(hass: HomeAssistant, flow_id: str, svg: str) -> None:
    """Serve ``svg`` as the QR code of ``flow_id``."""
    hass.data[DATA_QR_SVGS][flow_id] = svg


@callback
def async_remove_qr_svg(hass: HomeAssistant, flow_id: str) -> None:
    """Stop serving the QR code of ``flow_id``."""
    hass.data.get(DATA_QR_SVGS, {}).pop(flow_id, None)


@callback
def async_qr_url(hass: HomeAssistant, flow_id: str) -> str:
    """
    Return a signed, expiring URL for the QR code of ``flow_id``.

    The frontend loads it as a markdown image, which sends no auth header.
    """
    return async_sign_path(hass, QR_PATH.format(flow_id=flow_id), QR_URL_EXPIRY)


def generate_animated_qr_svg(qr1: qrcode.QRCode[Any], qr2: qrcode.QRCode[Any]) -> str:
    """
    Generate an animated SVG that alternates between two QR codes.

    The MitID app expects two QR codes to be scanned alternately.
    This function creates a single SVG with CSS animation that toggles
    between the two QR codes every 1 second.
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
        ".qr1{animation:swap 2s step-end infinite}"
        ".qr2{animation:swap 2s step-end infinite;animation-delay:1s;opacity:0}"
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

    url = QR_PATH
    name = "api:hass_aula:qr"

    async def get(self, request: web.Request, flow_id: str) -> web.Response:
        """Handle GET request for the QR code SVG."""
        svg = request.app[KEY_HASS].data.get(DATA_QR_SVGS, {}).get(flow_id)
        if svg is None:
            LOGGER.warning("QR view GET for flow %s: no SVG (returning 404)", flow_id)
            return web.Response(status=404, text="QR code not available")

        LOGGER.debug(
            "QR view GET for flow %s: serving SVG (%d bytes)", flow_id, len(svg)
        )
        return web.Response(
            body=svg,
            content_type="image/svg+xml",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
