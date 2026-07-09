"""The MyEdenred Portugal integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_TOKEN,
    PLATFORMS,
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

    from .client import MyEdenredPtClient
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
