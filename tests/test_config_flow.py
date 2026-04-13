"""Tests for the MyEdenred Portugal config flow."""

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.myedenred_pt.const import DOMAIN


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_user_step_normalizes_username_and_preserves_password(hass) -> None:
    """User setup should normalize the username before creating the entry."""
    with patch(
        "custom_components.myedenred_pt.config_flow.async_validate_input",
        AsyncMock(return_value={"title": "MyEdenred PT .com"}),
    ) as mock_validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: " User@Example.COM ",
                CONF_PASSWORD: " secret ",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyEdenred PT .com"
    assert result["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: " secret ",
    }
    mock_validate.assert_awaited_once_with(
        hass,
        {
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: " secret ",
        },
    )


async def test_user_step_rejects_blank_username_before_network_call(hass) -> None:
    """Blank usernames should fail before credentials are validated online."""
    with patch(
        "custom_components.myedenred_pt.config_flow.async_validate_input",
        AsyncMock(),
    ) as mock_validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "   ",
                CONF_PASSWORD: "secret",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_username"}
    mock_validate.assert_not_awaited()


async def test_reauth_uses_normalized_username_for_same_account(hass) -> None:
    """Reauth should treat case-only username differences as the same account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyEdenred PT .com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "old-password",
        },
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)

    with (
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ) as mock_reload,
        patch(
            "custom_components.myedenred_pt.config_flow.async_validate_input",
            AsyncMock(return_value={"title": "MyEdenred PT .com"}),
        ) as mock_validate,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: " USER@example.com ",
                CONF_PASSWORD: " new-password ",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: " new-password ",
    }
    assert entry.unique_id == "user@example.com"
    mock_validate.assert_awaited_once_with(
        hass,
        {
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: " new-password ",
        },
    )
    mock_reload.assert_awaited_once_with(entry.entry_id)
