"""Config flow for the Aula integration."""

from __future__ import annotations

import asyncio  # noqa: TC003
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers import selector
from slugify import slugify

from aula import authenticate

from .const import CONF_MITID_USERNAME, CONF_TOKEN_DATA, DOMAIN, LOGGER
from .qr_view import AulaQRView, generate_animated_qr_svg


class AulaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aula."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._mitid_username: str = ""
        self._token_data: dict[str, Any] | None = None
        self._auth_task: asyncio.Task[dict[str, Any]] | None = None
        self._qr_svg: str | None = None
        self._qr_view: AulaQRView | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the user step - enter MitID username."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._mitid_username = user_input[CONF_MITID_USERNAME]
            await self.async_set_unique_id(slugify(self._mitid_username))
            self._abort_if_unique_id_configured()
            return await self.async_step_mitid_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MITID_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def async_step_mitid_auth(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle MitID authentication with QR code display."""
        if not self._auth_task:
            self._auth_task = self.hass.async_create_task(
                self._async_authenticate(),
                "aula_mitid_auth",
            )
            self._register_qr_view()

        if self._auth_task.done():
            self._unregister_qr_view()
            if self._auth_task.exception():
                err = self._auth_task.exception()
                LOGGER.error("MitID authentication failed: %s", err)
                return self.async_abort(reason="auth_failed")

            self._token_data = self._auth_task.result()
            return self.async_create_entry(
                title=self._mitid_username,
                data={
                    CONF_MITID_USERNAME: self._mitid_username,
                    CONF_TOKEN_DATA: self._token_data,
                },
            )

        placeholders: dict[str, str] = {}
        if self._qr_svg:
            placeholders["qr_url"] = f"/api/aula/qr/{self.flow_id}"

        return self.async_show_progress(
            step_id="mitid_auth",
            progress_action="authenticating",
            description_placeholders=placeholders if self._qr_svg else None,
            progress_task=self._auth_task,
        )

    async def async_step_mitid_auth_done(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle completion of MitID auth progress."""
        self._unregister_qr_view()

        if self._auth_task and self._auth_task.exception():
            LOGGER.error("MitID authentication failed: %s", self._auth_task.exception())
            return self.async_abort(reason="auth_failed")

        if self._auth_task:
            self._token_data = self._auth_task.result()

        if self._reauth_entry:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data={
                    CONF_MITID_USERNAME: self._mitid_username,
                    CONF_TOKEN_DATA: self._token_data,
                },
            )

        return self.async_create_entry(
            title=self._mitid_username,
            data={
                CONF_MITID_USERNAME: self._mitid_username,
                CONF_TOKEN_DATA: self._token_data,
            },
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauth when token expires."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._mitid_username = entry_data[CONF_MITID_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauth confirmation - starts MitID auth."""
        if user_input is not None:
            return await self.async_step_mitid_auth()

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_MITID_USERNAME: self._mitid_username,
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration - allow changing MitID username."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._mitid_username = user_input[CONF_MITID_USERNAME]
            self._reauth_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            return await self.async_step_mitid_auth()

        reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        current_username = (
            reconfigure_entry.data.get(CONF_MITID_USERNAME, "")
            if reconfigure_entry
            else ""
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MITID_USERNAME,
                        default=current_username,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _async_authenticate(self) -> dict[str, Any]:
        """Run MitID authentication in background."""

        def on_qr_codes(qr1: Any, qr2: Any) -> None:
            self._qr_svg = generate_animated_qr_svg(qr1, qr2)
            if self._qr_view:
                self._qr_view.update_svg(self._qr_svg)

        return await authenticate(
            mitid_username=self._mitid_username,
            on_qr_codes=on_qr_codes,
        )

    def _register_qr_view(self) -> None:
        """Register a temporary HTTP view for serving the QR code SVG."""
        self._qr_view = AulaQRView(self.flow_id)
        self.hass.http.register_view(self._qr_view)

    def _unregister_qr_view(self) -> None:
        """Unregister the QR code HTTP view."""
        self._qr_view = None

    async def async_abort(self, *, reason: str, **kwargs: Any) -> ConfigFlowResult:
        """Handle flow abort - clean up resources."""
        self._unregister_qr_view()
        return super().async_abort(reason=reason, **kwargs)
