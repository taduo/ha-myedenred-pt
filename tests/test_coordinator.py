"""Unit tests for the MyEdenred Portugal coordinator helpers."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.myedenred_pt.client import MyEdenredPtAuthError
from custom_components.myedenred_pt.const import (
    CONF_KEEP_ALIVE_INTERVAL_MINUTES,
    CONF_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    get_keep_alive_interval_from_options,
    get_update_interval_from_options,
)
from custom_components.myedenred_pt.coordinator import (
    MyEdenredPtDataUpdateCoordinator,
)


def test_get_config_entry_update_interval_defaults_to_30_minutes() -> None:
    """Existing entries without options should keep the default cadence."""
    assert get_update_interval_from_options({}) == timedelta(minutes=30)


def test_get_config_entry_update_interval_uses_selected_option() -> None:
    """The configured options value should drive the coordinator interval."""
    assert get_update_interval_from_options(
        {CONF_UPDATE_INTERVAL_MINUTES: 60}
    ) == timedelta(minutes=60)


def test_get_keep_alive_interval_defaults_to_disabled() -> None:
    """Keep-alive should be opt-in while the token timeout is still unknown."""
    assert get_keep_alive_interval_from_options({}) is None


def test_get_keep_alive_interval_uses_selected_option() -> None:
    """The configured keep-alive value should become a timedelta."""
    assert get_keep_alive_interval_from_options(
        {CONF_KEEP_ALIVE_INTERVAL_MINUTES: 10}
    ) == timedelta(minutes=10)


async def test_auth_failure_triggers_home_assistant_reauthentication(hass) -> None:
    """Coordinator auth failures should enter Home Assistant's reauth flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_fetch_cards.side_effect = MyEdenredPtAuthError("expired")
    coordinator = MyEdenredPtDataUpdateCoordinator(hass, entry, client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
