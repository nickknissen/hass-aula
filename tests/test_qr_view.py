"""Tests for the MitID QR code view."""

from __future__ import annotations

import asyncio
import itertools
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_aula.const import CONF_MITID_USERNAME, DOMAIN

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.typing import ClientSessionGenerator

_QR_SVG = "custom_components.hass_aula.config_flow.generate_animated_qr_svg"


@pytest.fixture
async def login_waits_for_approval() -> AsyncIterator[None]:
    """Show the QR code, then wait for an approval that never comes."""
    approved = asyncio.Event()
    svg_number = itertools.count()

    async def fake_authenticate(**kwargs: Any) -> dict[str, Any]:
        kwargs["on_qr_codes"](None, None)
        await approved.wait()
        return MOCK_TOKEN_DATA

    with (
        patch(
            "custom_components.hass_aula.config_flow.authenticate",
            side_effect=fake_authenticate,
        ),
        patch(_QR_SVG, side_effect=lambda *_: f"<svg>{next(svg_number)}</svg>"),
    ):
        yield
    approved.set()


async def _show_qr(hass: HomeAssistant, username: str = MOCK_USERNAME) -> str:
    """Start a MitID app login and return the QR URL its form shows."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MITID_USERNAME: username}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mitid_qr"
    return result["description_placeholders"]["qr_url"]


@pytest.mark.usefixtures("login_waits_for_approval")
async def test_signed_qr_url_serves_the_svg(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The frontend loads the QR as an image, which sends no auth header."""
    qr_url = await _show_qr(hass)
    assert "authSig=" in qr_url

    client = await hass_client_no_auth()
    response = await client.get(qr_url)

    assert response.status == HTTPStatus.OK
    assert response.content_type == "image/svg+xml"
    assert await response.text() == "<svg>0</svg>"


@pytest.mark.usefixtures("login_waits_for_approval")
async def test_qr_view_refuses_an_unsigned_request(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Without the signature, anyone who learns the flow ID could fetch the QR."""
    qr_url = await _show_qr(hass)
    unsigned_url = qr_url.split("?", 1)[0]

    client = await hass_client_no_auth()
    response = await client.get(unsigned_url)

    assert response.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.usefixtures("login_waits_for_approval")
async def test_qr_is_gone_once_the_flow_is_closed(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """A signed URL keeps working until it expires, so the SVG itself must go."""
    qr_url = await _show_qr(hass)
    [flow] = hass.config_entries.flow.async_progress()

    hass.config_entries.flow.async_abort(flow["flow_id"])

    client = await hass_client_no_auth()
    response = await client.get(qr_url)
    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.usefixtures("login_waits_for_approval")
async def test_logins_share_one_route(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Each login used to add a route that stayed until Home Assistant restarted."""
    first_url = await _show_qr(hass, "first-user")
    second_url = await _show_qr(hass, "second-user")

    client = await hass_client_no_auth()
    assert await (await client.get(first_url)).text() == "<svg>0</svg>"
    assert await (await client.get(second_url)).text() == "<svg>1</svg>"
    qr_routes = [
        resource
        for resource in hass.http.app.router.resources()
        if resource.canonical.startswith("/api/hass_aula/qr")
    ]
    assert len(qr_routes) == 1
