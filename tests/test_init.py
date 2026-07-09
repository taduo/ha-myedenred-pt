"""Tests for MyEdenred Portugal config-entry setup and migration."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.myedenred_pt import async_migrate_entry, async_setup_entry
from custom_components.myedenred_pt.const import (
    CONF_KEEP_ALIVE_INTERVAL_MINUTES,
    CONF_TOKEN,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_setup_entry_passes_persisted_token_to_client(hass) -> None:
    """Setup should restore the session token without starting password login."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_TOKEN: "token-123",
        },
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    session = Mock()
    client = Mock()
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.myedenred_pt.client.MyEdenredPtClient",
            return_value=client,
        ) as client_class,
        patch(
            "custom_components.myedenred_pt.coordinator.MyEdenredPtDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(),
        ),
    ):
        assert await async_setup_entry(hass, entry)

    client_class.assert_called_once_with(
        session,
        "user@example.com",
        "secret",
        token="token-123",
    )
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    assert entry.runtime_data.client is client


async def test_migrate_tokenless_entry_to_minor_version_two(hass) -> None:
    """Existing entries should remain intact and request reauth during setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
        },
        unique_id="user@example.com",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
    }


async def test_setup_entry_schedules_configured_keep_alive(hass) -> None:
    """Setup should schedule the optional lightweight session keep-alive."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_TOKEN: "token-123",
        },
        options={CONF_KEEP_ALIVE_INTERVAL_MINUTES: 5},
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    session = Mock()
    client = Mock()
    client.async_keep_session_alive = AsyncMock()
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    unsubscribe = Mock()

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "homeassistant.helpers.event.async_track_time_interval",
            return_value=unsubscribe,
        ) as track_time_interval,
        patch(
            "custom_components.myedenred_pt.client.MyEdenredPtClient",
            return_value=client,
        ),
        patch(
            "custom_components.myedenred_pt.coordinator.MyEdenredPtDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(),
        ),
    ):
        assert await async_setup_entry(hass, entry)

    track_time_interval.assert_called_once()
    assert track_time_interval.call_args.args[0] is hass
    assert track_time_interval.call_args.args[2] == timedelta(minutes=5)
    assert track_time_interval.call_args.kwargs["name"] == (
        "myedenred_pt session keep-alive"
    )
