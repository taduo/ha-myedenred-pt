"""Unit tests for the MyEdenred Portugal client helpers."""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from custom_components.myedenred_pt.client import (
    MyEdenredCardBalance,
    MyEdenredDashboardData,
    MyEdenredPtAuthError,
    MyEdenredPtClient,
    MyEdenredPtMfaChallenge,
    MyEdenredPtMfaError,
    MyEdenredPtParseError,
    build_api_query_params,
    extract_auth_token,
    extract_authentication_result,
    extract_card_balance,
    extract_card_references,
    extract_cards_from_html,
    format_decimal_text,
    mask_card_number,
    parse_decimal_value,
)
from custom_components.myedenred_pt.const import (
    CARD_ACCOUNT_API_URL,
    CARDS_API_URL,
    LOGIN_API_URL,
    LOGIN_CHALLENGE_API_URL,
    LOGIN_CHALLENGE_RESEND_API_URL,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CARDS_PAYLOAD = json.loads(
    (FIXTURES_DIR / "cards_list.json").read_text(encoding="utf-8")
)
ACCOUNT_ONE_PAYLOAD = json.loads(
    (FIXTURES_DIR / "accountmovement_card_one.json").read_text(encoding="utf-8")
)
ACCOUNT_TWO_PAYLOAD = json.loads(
    (FIXTURES_DIR / "accountmovement_card_two.json").read_text(encoding="utf-8")
)
BALANCE_HTML = (FIXTURES_DIR / "balance_page.html").read_text(encoding="utf-8")


def test_extract_auth_token_returns_token() -> None:
    """The login parser should read the auth token from the payload."""
    payload = {"data": {"token": "token-123"}}

    assert extract_auth_token(payload) == "token-123"


def test_extract_auth_token_raises_auth_error_for_internal_code() -> None:
    """The login parser should map upstream auth failures to the generic message."""
    with pytest.raises(MyEdenredPtAuthError):
        extract_auth_token({"internalCode": "AUTH-001", "message": ["invalid"]})


def test_extract_authentication_result_returns_mfa_challenge() -> None:
    """The login parser should expose the MFA challenge without its secrets."""
    result = extract_authentication_result(
        {
            "data": {
                "challengeId": 123456,
                "challengeMessage": "Code sent to a masked contact",
                "resendTries": 3,
            }
        }
    )

    assert result == MyEdenredPtMfaChallenge(
        challenge_id=123456,
        challenge_message="Code sent to a masked contact",
        resend_tries=3,
    )


def test_extract_authentication_result_rejects_unknown_payload() -> None:
    """Unexpected successful login payloads should not be accepted."""
    with pytest.raises(MyEdenredPtParseError):
        extract_authentication_result({"data": {"customer": {}}})


def test_parse_decimal_value_supports_strings_and_numbers() -> None:
    """The numeric parser should handle the formats observed in the fixtures."""
    assert parse_decimal_value("12,74 €") == Decimal("12.74")
    assert parse_decimal_value("40.00") == Decimal("40.00")
    assert parse_decimal_value(12.74) == Decimal("12.74")


def test_format_decimal_text_uses_comma_separator() -> None:
    """Formatted balances should match the UI style used in the attributes."""
    assert format_decimal_text(Decimal("12.74")) == "12,74"


def test_mask_card_number_only_exposes_last_four_digits() -> None:
    """Card numbers should always be masked before being stored as attributes."""
    assert mask_card_number("1234 5678 9012 3456") == "**** 3456"
    assert mask_card_number(None) == "unknown"


def test_build_api_query_params_merges_common_values() -> None:
    """Every API request should include the common frontend query params."""
    assert build_api_query_params({"_": "123"}) == {
        "_": "123",
        "appVersion": "1.0",
        "appType": "PORTAL",
        "channel": "WEB",
    }


def test_extract_card_references_returns_cards_from_payload() -> None:
    """The cards list parser should normalize basic card metadata."""
    cards = extract_card_references(CARDS_PAYLOAD)

    assert len(cards) == 2
    assert cards[0].card_id == "101"
    assert cards[0].masked_card_number == "**** 3456"
    assert cards[1].card_status == "BLOCKED"


def test_extract_card_balance_returns_normalized_balance() -> None:
    """The account parser should return normalized card balance data."""
    card = extract_card_references(CARDS_PAYLOAD)[0]
    result = extract_card_balance(card, ACCOUNT_ONE_PAYLOAD)

    assert result.card_id == "101"
    assert result.masked_card_number == "**** 3456"
    assert result.balance == Decimal("12.74")
    assert result.balance_raw == "12,74"
    assert result.data_source == "api"
    assert result.owner_name == "Alex Silva"


def test_extract_cards_from_html_supports_observed_selector() -> None:
    """The HTML fallback parser should read all visible card balances."""
    cards = extract_cards_from_html(BALANCE_HTML)

    assert len(cards) == 2
    assert cards[0].masked_card_number == "**** 3456"
    assert cards[0].card_status == "ACTIVE"
    assert cards[0].balance == Decimal("12.74")
    assert cards[1].balance == Decimal("40.00")
    assert cards[1].data_source == "html"


def test_extract_cards_from_html_raises_when_missing() -> None:
    """Unexpected markup should be treated as a parse failure."""
    with pytest.raises(MyEdenredPtParseError):
        extract_cards_from_html("<html><body>No balance here</body></html>")


@pytest.mark.asyncio
async def test_async_fetch_cards_requires_persisted_token() -> None:
    """Polling without a token should request reauth without sending an OTP."""
    client = MyEdenredPtClient(object(), "user@example.com", "secret")
    client._async_fetch_cards_via_api = AsyncMock()

    with pytest.raises(MyEdenredPtAuthError):
        await client.async_fetch_cards()

    client._async_fetch_cards_via_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_fetch_cards_clears_expired_token_without_login() -> None:
    """Rejected session tokens should not start MFA in the background."""
    client = MyEdenredPtClient(
        object(),
        "user@example.com",
        "secret",
        token="expired-token",
    )
    client._async_fetch_cards_via_api = AsyncMock(
        side_effect=MyEdenredPtAuthError("expired")
    )

    with pytest.raises(MyEdenredPtAuthError):
        await client.async_fetch_cards()

    assert client.token is None
    client._async_fetch_cards_via_api.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_fetch_cards_uses_html_fallback_when_api_parsing_fails() -> None:
    """HTML parsing should be attempted when the API shape is no longer usable."""
    expected = MyEdenredDashboardData(
        cards=(
            MyEdenredCardBalance(
                key="html_1",
                card_id="html_1",
                masked_card_number="**** 3456",
                card_status="ACTIVE",
                balance=Decimal("12.74"),
                balance_raw="12,74",
                data_source="html",
            ),
        )
    )
    client = MyEdenredPtClient(
        object(),
        "user@example.com",
        "secret",
        token="token-123",
    )
    client._async_fetch_cards_via_api = AsyncMock(
        side_effect=MyEdenredPtParseError("bad payload")
    )
    client._async_fetch_cards_via_html = AsyncMock(return_value=expected)

    result = await client.async_fetch_cards()

    assert result == expected
    client._async_fetch_cards_via_html.assert_awaited_once()


class _FakeResponse:
    """Minimal async context manager used by the request wiring test."""

    def __init__(self, status: int = 200, text: str = "{}") -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _RecordingSession:
    """Capture outbound aiohttp request arguments without doing network IO."""

    def __init__(self, responses: list[tuple[int, object]] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.responses = list(responses or [])

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        if self.responses:
            status, payload = self.responses.pop(0)
            return _FakeResponse(status, json.dumps(payload))
        return _FakeResponse()


@pytest.mark.asyncio
async def test_async_begin_authentication_returns_challenge() -> None:
    """Password login should retain the challenge for the config flow."""
    session = _RecordingSession(
        [
            (
                200,
                {
                    "data": {
                        "challengeId": 123456,
                        "challengeMessage": "Code sent",
                        "resendTries": 3,
                    }
                },
            )
        ]
    )
    client = MyEdenredPtClient(session, "user@example.com", "secret")

    challenge = await client.async_begin_authentication()

    assert challenge == MyEdenredPtMfaChallenge(
        challenge_id=123456,
        challenge_message="Code sent",
        resend_tries=3,
    )
    assert client.token is None
    assert session.calls[0][0:2] == ("post", LOGIN_API_URL)
    assert session.calls[0][2]["json"] == {
        "userId": "user@example.com",
        "password": "secret",
    }


@pytest.mark.asyncio
async def test_async_begin_authentication_supports_direct_token() -> None:
    """Accounts without MFA should retain their direct login token."""
    session = _RecordingSession([(200, {"data": {"token": "token-123"}})])
    client = MyEdenredPtClient(session, "user@example.com", "secret")

    challenge = await client.async_begin_authentication()

    assert challenge is None
    assert client.token == "token-123"


@pytest.mark.asyncio
async def test_async_complete_mfa_uses_captured_request_shape() -> None:
    """MFA completion should send all fields required by the portal."""
    session = _RecordingSession([(200, {"data": {"token": "token-456"}})])
    client = MyEdenredPtClient(session, "user@example.com", "secret")

    token = await client.async_complete_mfa(123456, "12345")

    assert token == "token-456"
    assert client.token == "token-456"
    assert session.calls[0][0:2] == ("post", LOGIN_CHALLENGE_API_URL)
    assert session.calls[0][2]["json"] == {
        "userId": "user@example.com",
        "password": "secret",
        "authenticationMfaProcessId": 123456,
        "token": "12345",
    }


@pytest.mark.asyncio
async def test_async_complete_mfa_rejects_invalid_code() -> None:
    """An upstream MFA rejection should be distinguishable in the flow."""
    session = _RecordingSession([(409, {"internalCode": "invalid-code"})])
    client = MyEdenredPtClient(session, "user@example.com", "secret")

    with pytest.raises(MyEdenredPtMfaError):
        await client.async_complete_mfa("challenge-123", "00000")


@pytest.mark.asyncio
async def test_async_resend_mfa_replaces_challenge() -> None:
    """Resending should return the replacement challenge identifier."""
    session = _RecordingSession(
        [
            (
                200,
                {
                    "data": {
                        "challengeId": "challenge-456",
                        "challengeMessage": "New code sent",
                        "resendTries": 2,
                    }
                },
            )
        ]
    )
    client = MyEdenredPtClient(session, "user@example.com", "secret")

    challenge = await client.async_resend_mfa("challenge-123")

    assert challenge.challenge_id == "challenge-456"
    assert challenge.resend_tries == 2
    assert session.calls[0][0:2] == ("post", LOGIN_CHALLENGE_RESEND_API_URL)
    assert session.calls[0][2]["json"] == {
        "authenticationMfaProcessId": "challenge-123"
    }


@pytest.mark.asyncio
async def test_async_request_text_adds_common_params_and_auth_header() -> None:
    """Protected API calls should match the live frontend request shape."""
    session = _RecordingSession()
    client = MyEdenredPtClient(
        session,
        "user@example.com",
        "secret",
        token="token-123",
    )

    await client._async_request_text("get", CARDS_API_URL)
    await client._async_request_text(
        "get",
        CARD_ACCOUNT_API_URL.format(card_id="101"),
        params={"_": "123"},
    )

    assert session.calls[0][2]["headers"] == {"Authorization": "token-123"}
    assert session.calls[0][2]["params"] == {
        "appVersion": "1.0",
        "appType": "PORTAL",
        "channel": "WEB",
    }
    assert session.calls[1][2]["params"] == {
        "_": "123",
        "appVersion": "1.0",
        "appType": "PORTAL",
        "channel": "WEB",
    }
