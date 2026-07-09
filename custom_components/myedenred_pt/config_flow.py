"""Config flow for the MyEdenred Portugal integration."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import (
    MyEdenredPtAuthError,
    MyEdenredPtClient,
    MyEdenredPtConnectionError,
    MyEdenredPtMfaChallenge,
    MyEdenredPtMfaError,
    MyEdenredPtParseError,
)
from .const import (
    CONF_KEEP_ALIVE_INTERVAL_MINUTES,
    CONF_TOKEN,
    CONF_TOKEN_OBTAINED_AT,
    CONF_UPDATE_INTERVAL_MINUTES,
    DEFAULT_KEEP_ALIVE_INTERVAL_MINUTES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    KEEP_ALIVE_INTERVAL_OPTION_LABELS,
    UPDATE_INTERVAL_OPTION_LABELS,
    is_valid_username,
    normalize_keep_alive_interval_minutes,
    normalize_update_interval_minutes,
    normalize_username,
    title_for_username,
)

_LOGGER = logging.getLogger(__name__)

CONF_OTP = "otp"
CONF_RESEND_CODE = "resend_code"
_OTP_PATTERN = re.compile(r"\d{5}")
_OptionsFlowBase = getattr(
    config_entries,
    "OptionsFlowWithReload",
    config_entries.OptionsFlow,
)


def normalize_credentials(user_input: dict[str, str]) -> dict[str, str]:
    """Normalize user-provided credentials without altering the password."""
    return {
        CONF_USERNAME: normalize_username(user_input[CONF_USERNAME]),
        CONF_PASSWORD: user_input[CONF_PASSWORD],
    }


def build_client(
    hass: HomeAssistant,
    user_input: dict[str, str],
) -> MyEdenredPtClient:
    """Build a client for an interactive authentication attempt."""
    session = async_get_clientsession(hass)
    return MyEdenredPtClient(
        session,
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
    )


class MyEdenredPtConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyEdenred Portugal."""

    VERSION = 1
    MINOR_VERSION = 2

    _pending_client: MyEdenredPtClient | None = None
    _pending_data: dict[str, str] | None = None
    _mfa_challenge: MyEdenredPtMfaChallenge | None = None

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_data = normalize_credentials(user_input)

            if not is_valid_username(normalized_data[CONF_USERNAME]):
                errors["base"] = "invalid_username"
            else:
                try:
                    await self.async_set_unique_id(normalized_data[CONF_USERNAME])
                    self._abort_if_unique_id_configured()
                    result = await self._async_begin_authentication(normalized_data)
                except MyEdenredPtAuthError:
                    errors["base"] = "invalid_auth"
                except MyEdenredPtConnectionError:
                    errors["base"] = "cannot_connect"
                except MyEdenredPtParseError:
                    errors["base"] = "cannot_parse"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error while validating MyEdenred credentials"
                    )
                    errors["base"] = "unknown"
                else:
                    return result

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Handle a reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Confirm before sending a new MFA code."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            data = {
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            }
            try:
                return await self._async_begin_authentication(data)
            except MyEdenredPtAuthError:
                return await self.async_step_reauth_credentials(
                    errors={"base": "invalid_auth"}
                )
            except MyEdenredPtConnectionError:
                errors["base"] = "cannot_connect"
            except MyEdenredPtParseError:
                errors["base"] = "cannot_parse"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error while starting MyEdenred reauthentication"
                )
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"account": entry.title},
        )

    async def async_step_reauth_credentials(
        self,
        user_input: dict[str, str] | None = None,
        *,
        errors: dict[str, str] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect a replacement password when the stored one is rejected."""
        form_errors = dict(errors or {})
        entry = self._get_reauth_entry()

        if user_input is not None:
            data = {
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await self.async_set_unique_id(data[CONF_USERNAME])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return await self._async_begin_authentication(data)
            except MyEdenredPtAuthError:
                form_errors["base"] = "invalid_auth"
            except MyEdenredPtConnectionError:
                form_errors["base"] = "cannot_connect"
            except MyEdenredPtParseError:
                form_errors["base"] = "cannot_parse"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error while updating MyEdenred credentials"
                )
                form_errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    )
                }
            ),
            errors=form_errors,
            description_placeholders={"account": entry.title},
        )

    async def async_step_mfa(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Validate or resend the MyEdenred MFA code."""
        errors: dict[str, str] = {}
        client = self._pending_client
        challenge = self._mfa_challenge

        if client is None or self._pending_data is None or challenge is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            if user_input.get(CONF_RESEND_CODE):
                try:
                    self._mfa_challenge = await client.async_resend_mfa(
                        challenge.challenge_id
                    )
                except MyEdenredPtMfaError:
                    errors["base"] = "cannot_resend"
                except MyEdenredPtConnectionError:
                    errors["base"] = "cannot_connect"
                except MyEdenredPtParseError:
                    errors["base"] = "cannot_parse"
                except Exception:
                    _LOGGER.exception("Unexpected error while resending MyEdenred MFA")
                    errors["base"] = "unknown"
                else:
                    errors["base"] = "code_resent"
            else:
                code = str(user_input.get(CONF_OTP, "")).strip()
                if _OTP_PATTERN.fullmatch(code) is None:
                    errors["base"] = "invalid_code"
                else:
                    try:
                        await client.async_complete_mfa(
                            challenge.challenge_id,
                            code,
                        )
                        return await self._async_finish_authentication()
                    except MyEdenredPtAuthError:
                        errors["base"] = "invalid_code"
                    except MyEdenredPtConnectionError:
                        errors["base"] = "cannot_connect"
                    except MyEdenredPtParseError:
                        errors["base"] = "cannot_parse"
                    except Exception:
                        _LOGGER.exception(
                            "Unexpected error while validating MyEdenred MFA"
                        )
                        errors["base"] = "unknown"

        return self._show_mfa_form(errors)

    async def _async_begin_authentication(
        self,
        data: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Begin authentication and continue to MFA or completion."""
        client = build_client(self.hass, data)
        challenge = await client.async_begin_authentication()
        self._pending_client = client
        self._pending_data = data
        self._mfa_challenge = challenge

        if challenge is not None:
            return self._show_mfa_form({})
        return await self._async_finish_authentication()

    async def _async_finish_authentication(
        self,
    ) -> config_entries.ConfigFlowResult:
        """Validate the token, then create or update the config entry."""
        client = self._pending_client
        data = self._pending_data
        if client is None or data is None or client.token is None:
            return self.async_abort(reason="unknown")

        await client.async_fetch_cards()
        entry_data = {
            **data,
            CONF_TOKEN: client.token,
            CONF_TOKEN_OBTAINED_AT: datetime.now(UTC).isoformat(),
        }
        title = title_for_username(data[CONF_USERNAME])

        if self.source == config_entries.SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            await self.async_set_unique_id(data[CONF_USERNAME])
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                entry,
                data_updates=entry_data,
            )

        return self.async_create_entry(title=title, data=entry_data)

    def _show_mfa_form(
        self,
        errors: dict[str, str],
    ) -> config_entries.ConfigFlowResult:
        """Render the active MFA challenge form."""
        challenge = self._mfa_challenge
        if challenge is None:
            return self.async_abort(reason="unknown")

        schema: dict[vol.Marker, Any] = {
            vol.Optional(CONF_OTP, default=""): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                    autocomplete="one-time-code",
                )
            )
        }
        if challenge.resend_tries > 0:
            schema[vol.Optional(CONF_RESEND_CODE, default=False)] = bool

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "challenge_message": challenge.challenge_message,
                "resend_tries": str(challenge.resend_tries),
            },
        )

    @staticmethod
    def _build_schema(defaults: dict[str, str] | None) -> vol.Schema:
        """Build the flow schema."""
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=defaults.get(CONF_USERNAME, ""),
                ): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT,
                        autocomplete="username",
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return MyEdenredPtOptionsFlowHandler()


class MyEdenredPtOptionsFlowHandler(_OptionsFlowBase):
    """Handle the options flow for MyEdenred Portugal."""

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            keep_alive_interval = normalize_keep_alive_interval_minutes(
                user_input[CONF_KEEP_ALIVE_INTERVAL_MINUTES]
            )
            return self.async_create_entry(
                data={
                    CONF_KEEP_ALIVE_INTERVAL_MINUTES: keep_alive_interval,
                    CONF_UPDATE_INTERVAL_MINUTES: normalize_update_interval_minutes(
                        user_input[CONF_UPDATE_INTERVAL_MINUTES]
                    ),
                }
            )

        current_keep_alive_interval = normalize_keep_alive_interval_minutes(
            self.config_entry.options.get(
                CONF_KEEP_ALIVE_INTERVAL_MINUTES,
                DEFAULT_KEEP_ALIVE_INTERVAL_MINUTES,
            )
        )
        current_interval = normalize_update_interval_minutes(
            self.config_entry.options.get(
                CONF_UPDATE_INTERVAL_MINUTES,
                DEFAULT_UPDATE_INTERVAL_MINUTES,
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL_MINUTES,
                        default=str(current_interval),
                    ): vol.In(UPDATE_INTERVAL_OPTION_LABELS),
                    vol.Required(
                        CONF_KEEP_ALIVE_INTERVAL_MINUTES,
                        default=str(current_keep_alive_interval),
                    ): vol.In(KEEP_ALIVE_INTERVAL_OPTION_LABELS),
                }
            ),
        )
