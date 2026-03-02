"""Tests for Aula config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hass_aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    CONF_WIDGETS,
    DOMAIN,
)

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME, make_config_entry

# Patch target for widget fetching (avoids network calls in tests)
_FETCH_WIDGETS = "custom_components.hass_aula.config_flow.AulaFlowHandler._async_fetch_widgets"


async def _advance_to_select_widgets(hass, flow_id):
    """Drive the flow from SHOW_PROGRESS (if any) to the select_widgets FORM.

    With an eager mock, auth may complete synchronously and we go straight to
    FORM.  With a slower mock we get SHOW_PROGRESS first.  This helper handles
    both so individual tests stay focused on what they're actually testing.
    """
    # Let any in-flight tasks run (needed when auth is truly async)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)

    # If we're still in progress, let tasks run and poll once more
    if result["type"] is FlowResultType.SHOW_PROGRESS:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(flow_id)

    return result


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.hass_aula.config_flow.authenticate",
            return_value=MOCK_TOKEN_DATA,
        ),
        patch(_FETCH_WIDGETS, return_value=[]),
    ):
        # Submit username
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )

        # Advance through any progress steps to select_widgets
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            result = await _advance_to_select_widgets(hass, result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_widgets"

        # Submit widget selection → CREATE_ENTRY
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_WIDGETS: []},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"][CONF_MITID_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_TOKEN_DATA] == MOCK_TOKEN_DATA


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow aborts for duplicate entry."""
    with (
        patch(
            "custom_components.hass_aula.config_flow.authenticate",
            return_value=MOCK_TOKEN_DATA,
        ),
        patch(_FETCH_WIDGETS, return_value=[]),
    ):
        # Complete first install
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            result = await _advance_to_select_widgets(hass, result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_widgets"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_WIDGETS: []}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # Try to add the same account again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_auth_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow handles auth failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "custom_components.hass_aula.config_flow.authenticate",
        side_effect=RuntimeError("MitID authentication failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )

        # May get SHOW_PROGRESS or ABORT depending on task timing
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow."""
    entry = make_config_entry()
    entry.add_to_hass(hass)

    await entry.start_reauth_flow(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow_id = flows[0]["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.hass_aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    entry = make_config_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    flow_id = result["flow_id"]

    new_username = "new_user"
    with patch(
        "custom_components.hass_aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_MITID_USERNAME: new_username},
        )

        if result["type"] is FlowResultType.SHOW_PROGRESS:
            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
