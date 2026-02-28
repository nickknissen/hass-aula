"""Config flow for the Aula integration."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from aula import authenticate
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers import selector
from slugify import slugify

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
        self._qr_ready_task: asyncio.Task[None] | None = None
        self._qr_ready_event: asyncio.Event | None = None
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
            LOGGER.debug("Starting MitID auth flow for %s", self._mitid_username)
            self._qr_ready_event = asyncio.Event()
            self._qr_ready_task = self.hass.async_create_task(
                self._wait_for_qr_ready(),
                "hass_aula_qr_ready",
            )
            # Register the view BEFORE creating the auth task.
            # The task starts eagerly, so on_qr_codes fires synchronously during
            # task creation — _qr_view must already exist at that point.
            self._register_qr_view()
            LOGGER.debug("QR view registered at /api/hass_aula/qr/%s", self.flow_id)
            self._auth_task = self.hass.async_create_task(
                self._async_authenticate(),
                "hass_aula_mitid_auth",
            )
            LOGGER.debug(
                "Auth task created. qr_svg set=%s, "
                "qr_view has svg=%s, qr_ready_event set=%s",
                self._qr_svg is not None,
                self._qr_view is not None and self._qr_view._svg is not None,  # noqa: SLF001
                self._qr_ready_event.is_set(),
            )

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

        # QR is ready — transition out of progress via progress_done, then show QR form.
        # SHOW_PROGRESS can only transition to SHOW_PROGRESS or SHOW_PROGRESS_DONE;
        # jumping directly to SHOW_FORM raises a ValueError.
        if self._qr_svg:
            LOGGER.debug("QR ready, transitioning to QR form step via progress_done")
            return self.async_show_progress_done(next_step_id="mitid_qr")

        # QR not yet generated — show spinner while waiting.
        progress_task = (
            self._qr_ready_task
            if self._qr_ready_task and not self._qr_ready_task.done()
            else self._auth_task
        )
        LOGGER.debug(
            "Showing progress spinner, progress_task=%s",
            "qr_ready" if progress_task is self._qr_ready_task else "auth",
        )
        return self.async_show_progress(
            step_id="mitid_auth",
            progress_action="authenticating",
            progress_task=progress_task,
        )

    async def async_step_mitid_auth_done(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle completion of MitID auth progress."""
        LOGGER.debug(
            "mitid_auth_done called: auth_task done=%s, qr_svg set=%s",
            self._auth_task.done() if self._auth_task else "no task",
            self._qr_svg is not None,
        )
        # The QR-ready task finished but auth is still running.
        # SHOW_PROGRESS does not render description_placeholders in the frontend,
        # so switch to a FORM step which does render its description markdown.
        if self._auth_task and not self._auth_task.done():
            return await self.async_step_mitid_qr()

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

    async def async_step_mitid_qr(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show QR code step; FORM renders markdown images, PROGRESS does not."""
        if user_input is not None:
            # User clicked Submit after approving on their phone.
            if self._auth_task and self._auth_task.done():
                self._unregister_qr_view()
                if self._auth_task.exception():
                    LOGGER.error(
                        "MitID authentication failed: %s", self._auth_task.exception()
                    )
                    return self.async_abort(reason="auth_failed")
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
            # Auth not finished yet — re-show with the latest QR (on_qr_codes
            # keeps updating the view in the background).
            LOGGER.debug("Submit pressed but auth not done yet, re-showing QR form")

        LOGGER.debug(
            "Showing QR form: qr_url=/api/hass_aula/qr/%s, auth_done=%s",
            self.flow_id,
            self._auth_task.done() if self._auth_task else "no task",
        )
        return self.async_show_form(
            step_id="mitid_qr",
            data_schema=vol.Schema({}),
            description_placeholders={"qr_url": f"/api/hass_aula/qr/{self.flow_id}"},
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
            LOGGER.debug(
                "on_qr_codes called: qr1=%s, qr2=%s, _qr_view=%s",
                type(qr1).__name__,
                type(qr2).__name__,
                "set" if self._qr_view else "None",
            )
            self._qr_svg = generate_animated_qr_svg(qr1, qr2)
            LOGGER.debug("QR SVG generated (%d bytes)", len(self._qr_svg))
            if self._qr_view:
                self._qr_view.update_svg(self._qr_svg)
                LOGGER.debug("QR SVG written to view")
            else:
                LOGGER.warning(
                    "on_qr_codes fired but _qr_view is None — SVG not served"
                )
            if self._qr_ready_event:
                self._qr_ready_event.set()
                LOGGER.debug("QR ready event set")

        LOGGER.debug("Calling aula.authenticate for %s", self._mitid_username)
        result = await authenticate(
            mitid_username=self._mitid_username,
            on_qr_codes=on_qr_codes,
        )
        LOGGER.debug("aula.authenticate returned successfully")
        return result

    async def _wait_for_qr_ready(self) -> None:
        """Wait until QR codes have been generated."""
        if self._qr_ready_event:
            await self._qr_ready_event.wait()

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
