"""Data update coordinator for MyEdenred Portugal."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    MyEdenredDashboardData,
    MyEdenredPtAuthError,
    MyEdenredPtClient,
    MyEdenredPtConnectionError,
    MyEdenredPtParseError,
)
from .const import DOMAIN, get_update_interval_from_options

_LOGGER = logging.getLogger(__name__)


def get_config_entry_update_interval(entry: ConfigEntry) -> timedelta:
    """Return the configured update interval for a config entry."""
    return get_update_interval_from_options(entry.options)


class MyEdenredPtDataUpdateCoordinator(DataUpdateCoordinator[MyEdenredDashboardData]):
    """Coordinate data updates for a MyEdenred account."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MyEdenredPtClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=get_config_entry_update_interval(entry),
        )
        self.config_entry = entry
        self.client = client

    async def _async_update_data(self) -> MyEdenredDashboardData:
        """Fetch data from MyEdenred."""
        try:
            return await self.client.async_fetch_cards()
        except MyEdenredPtAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (MyEdenredPtConnectionError, MyEdenredPtParseError) as err:
            raise UpdateFailed(str(err)) from err
