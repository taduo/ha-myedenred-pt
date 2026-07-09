"""Tests for the MyEdenred Portugal config flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.myedenred_pt.client import (
    MyEdenredPtAuthError,
    MyEdenredPtMfaChallenge,
)
from custom_components.myedenred_pt.const import CONF_TOKEN, DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def make_client(
    *,
    challenge: MyEdenredPtMfaChallenge | None = None,
    token: str | None = "token-123",
) -> Mock:
    """Create a mocked interactive authentication client."""
    client = Mock()
    client.token = token
    client.async_begin_authentication = AsyncMock(return_value=challenge)
    client.async_complete_mfa = AsyncMock(return_value=token)
    client.async_resend_mfa = AsyncMock(return_value=challenge)
    client.async_fetch_cards = AsyncMock()
    return client


async def test_user_step_normalizes_username_and_preserves_password(hass) -> None:
    """User setup should normalize the username before creating the entry."""
    client = make_client()
    with patch(
        "custom_components.myedenred_pt.config_flow.build_client",
        return_value=client,
    ) as mock_build:
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
        CONF_TOKEN: "token-123",
    }
    mock_build.assert_called_once_with(
        hass,
        {
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: " secret ",
        },
    )
    client.async_begin_authentication.assert_awaited_once()
    client.async_fetch_cards.assert_awaited_once()


async def test_user_step_rejects_blank_username_before_network_call(hass) -> None:
    """Blank usernames should fail before credentials are validated online."""
    with patch(
        "custom_components.myedenred_pt.config_flow.build_client",
    ) as mock_build:
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
    mock_build.assert_not_called()


async def test_user_step_completes_mfa_before_creating_entry(hass) -> None:
    """The entry should only be created after a valid five-digit code."""
    challenge = MyEdenredPtMfaChallenge(
        challenge_id="challenge-123",
        challenge_message="Code sent",
        resend_tries=3,
    )
    client = make_client(challenge=challenge, token="token-456")

    with patch(
        "custom_components.myedenred_pt.config_flow.build_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "secret",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp": "12345", "resend_code": False},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == "token-456"
    client.async_complete_mfa.assert_awaited_once_with("challenge-123", "12345")
    client.async_fetch_cards.assert_awaited_once()


async def test_user_step_rejects_invalid_mfa_format(hass) -> None:
    """Invalid local OTP input should not call MyEdenred."""
    challenge = MyEdenredPtMfaChallenge("challenge-123", "Code sent", 3)
    client = make_client(challenge=challenge)

    with patch(
        "custom_components.myedenred_pt.config_flow.build_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "secret",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp": "1234", "resend_code": False},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_code"}
    client.async_complete_mfa.assert_not_awaited()


async def test_user_step_resends_mfa_and_uses_replacement_challenge(hass) -> None:
    """Resend should replace the challenge used for OTP validation."""
    first = MyEdenredPtMfaChallenge("challenge-123", "Code sent", 3)
    replacement = MyEdenredPtMfaChallenge("challenge-456", "New code sent", 2)
    client = make_client(challenge=first, token="token-456")
    client.async_resend_mfa = AsyncMock(return_value=replacement)

    with patch(
        "custom_components.myedenred_pt.config_flow.build_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "secret",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp": "", "resend_code": True},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "code_resent"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp": "12345", "resend_code": False},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    client.async_resend_mfa.assert_awaited_once_with("challenge-123")
    client.async_complete_mfa.assert_awaited_once_with("challenge-456", "12345")


async def test_reauth_uses_stored_password_and_replaces_token(hass) -> None:
    """Reauth should send MFA only after confirmation and reload the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyEdenred PT .com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "old-password",
            CONF_TOKEN: "expired-token",
        },
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    challenge = MyEdenredPtMfaChallenge("challenge-123", "Code sent", 3)
    client = make_client(challenge=challenge, token="new-token")

    with (
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ) as mock_reload,
        patch(
            "custom_components.myedenred_pt.config_flow.build_client",
            return_value=client,
        ) as mock_build,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        mock_build.assert_not_called()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "otp": "12345",
                "resend_code": False,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "old-password",
        CONF_TOKEN: "new-token",
    }
    assert entry.unique_id == "user@example.com"
    mock_build.assert_called_once_with(
        hass,
        {
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "old-password",
        },
    )
    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_reauth_can_replace_rejected_stored_password(hass) -> None:
    """A changed password should be recoverable within reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MyEdenred PT .com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "old-password",
            CONF_TOKEN: "expired-token",
        },
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    rejected_client = make_client(token=None)
    rejected_client.async_begin_authentication = AsyncMock(
        side_effect=MyEdenredPtAuthError("invalid")
    )
    replacement_client = make_client(token="new-token")

    with (
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.myedenred_pt.config_flow.build_client",
            side_effect=[rejected_client, replacement_client],
        ),
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
            {},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_credentials"
        assert result["errors"] == {"base": "invalid_auth"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_TOKEN] == "new-token"
