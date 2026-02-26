"""Tests for Aula config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.aula.const import (
    CONF_MITID_USERNAME,
    CONF_TOKEN_DATA,
    DOMAIN,
)

from .conftest import MOCK_TOKEN_DATA, MOCK_USERNAME


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

    with patch(
        "custom_components.aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )

        # Should show progress for MitID auth
        # The auth task completes immediately in tests since authenticate is mocked
        # We need to wait for the progress to complete
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
            )

        if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
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
    # First, set up an existing entry
    with patch(
        "custom_components.aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )
        # Complete the flow
        while result["type"] in (
            FlowResultType.SHOW_PROGRESS,
            FlowResultType.SHOW_PROGRESS_DONE,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
            )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # Now try to add the same account
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
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
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "custom_components.aula.config_flow.authenticate",
        side_effect=RuntimeError("MitID authentication failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: MOCK_USERNAME},
        )

        # Progress should eventually abort
        while result["type"] is FlowResultType.SHOW_PROGRESS:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow."""
    # Create an existing entry
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_MITID_USERNAME: MOCK_USERNAME,
            CONF_TOKEN_DATA: MOCK_TOKEN_DATA,
        },
        source="user",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        # Complete the auth flow
        while result["type"] in (
            FlowResultType.SHOW_PROGRESS,
            FlowResultType.SHOW_PROGRESS_DONE,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_MITID_USERNAME: MOCK_USERNAME,
            CONF_TOKEN_DATA: MOCK_TOKEN_DATA,
        },
        source="user",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_username = "new_user"
    with patch(
        "custom_components.aula.config_flow.authenticate",
        return_value=MOCK_TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MITID_USERNAME: new_username},
        )

        while result["type"] in (
            FlowResultType.SHOW_PROGRESS,
            FlowResultType.SHOW_PROGRESS_DONE,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
