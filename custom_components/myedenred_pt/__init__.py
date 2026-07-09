"""The MyEdenred Portugal integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_TOKEN,
    CONF_TOKEN_OBTAINED_AT,
    DOMAIN,
    PLATFORMS,
    get_keep_alive_interval_from_options,
    is_valid_username,
    normalize_username,
    title_for_username,
)

_LOGGER = logging.getLogger(__name__)
CONF_PASSWORD = "password"
CONF_USERNAME = "username"

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .client import MyEdenredPtClient
    from .coordinator import MyEdenredPtDataUpdateCoordinator


@dataclass
class MyEdenredPtRuntimeData:
    """Runtime objects stored on the config entry."""

    client: MyEdenredPtClient
    coordinator: MyEdenredPtDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration from YAML."""
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older config entries to the latest normalized username format."""
    if entry.version > 1:
        return False

    if entry.version == 1 and entry.minor_version < 2:
        updates: dict[str, Any] = {"version": 1, "minor_version": 2}

        if entry.minor_version < 1:
            normalized_username = normalize_username(entry.data.get(CONF_USERNAME, ""))
            if is_valid_username(normalized_username):
                updates["data"] = {
                    **entry.data,
                    CONF_USERNAME: normalized_username,
                }
                updates["unique_id"] = normalized_username
                updates["title"] = title_for_username(normalized_username)
            else:
                _LOGGER.warning(
                    "Skipping MyEdenred username normalization for entry %s "
                    "because the stored value is invalid.",
                    entry.entry_id,
                )

        hass.config_entries.async_update_entry(entry, **updates)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyEdenred Portugal from a config entry."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.event import async_track_time_interval

    from .client import (
        MyEdenredPtAuthError,
        MyEdenredPtClient,
        MyEdenredPtConnectionError,
    )
    from .coordinator import MyEdenredPtDataUpdateCoordinator

    session = async_get_clientsession(hass)
    client = MyEdenredPtClient(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        token=entry.data.get(CONF_TOKEN),
    )
    coordinator = MyEdenredPtDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MyEdenredPtRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if keep_alive_interval := get_keep_alive_interval_from_options(entry.options):
        reauth_started = False

        async def _async_keep_session_alive(_now: datetime) -> None:
            nonlocal reauth_started
            if reauth_started:
                return
            try:
                await client.async_keep_session_alive()
            except MyEdenredPtAuthError:
                reauth_started = True
                _LOGGER.info(
                    "MyEdenred session for %s expired during keep-alive%s; "
                    "starting reauthentication",
                    entry.title,
                    _format_token_age(entry),
                )
                entry.async_start_reauth(hass)
            except MyEdenredPtConnectionError as err:
                _LOGGER.debug(
                    "MyEdenred keep-alive failed for %s: %s",
                    entry.title,
                    err,
                )

        _LOGGER.debug(
            "Enabling MyEdenred session keep-alive every %s minutes for %s",
            keep_alive_interval.total_seconds() / 60,
            entry.title,
        )
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                _async_keep_session_alive,
                keep_alive_interval,
                name=f"{DOMAIN} session keep-alive",
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _format_token_age(entry: ConfigEntry) -> str:
    """Return a safe, approximate age suffix for diagnostics."""
    raw_obtained_at = entry.data.get(CONF_TOKEN_OBTAINED_AT)
    if not isinstance(raw_obtained_at, str):
        return ""

    try:
        obtained_at = datetime.fromisoformat(raw_obtained_at)
    except ValueError:
        return ""

    if obtained_at.tzinfo is None:
        obtained_at = obtained_at.replace(tzinfo=UTC)

    age_seconds = (
        datetime.now(UTC) - obtained_at.astimezone(UTC)
    ).total_seconds()
    if age_seconds < 0:
        return ""
    if age_seconds < 3600:
        return f" after about {round(age_seconds / 60)} minutes"
    return f" after about {age_seconds / 3600:.1f} hours"
