"""Unit tests for the MyEdenred Portugal client helpers."""

from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from custom_components.myedenred_pt.client import (
    MyEdenredCardBalance,
    MyEdenredDashboardData,
    MyEdenredPtAuthError,
    MyEdenredPtClient,
    MyEdenredPtParseError,
    extract_auth_token,
    extract_card_balance,
    extract_card_references,
    extract_cards_from_html,
    format_decimal_text,
    mask_card_number,
    parse_decimal_value,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CARDS_PAYLOAD = json.loads((FIXTURES_DIR / "cards_list.json").read_text(encoding="utf-8"))
ACCOUNT_ONE_PAYLOAD = json.loads(
    (FIXTURES_DIR / "accountmovement_card_one.json").read_text(encoding="utf-8")
)
ACCOUNT_TWO_PAYLOAD = json.loads(
    (FIXTURES_DIR / "accountmovement_card_two.json").read_text(encoding="utf-8")
)
BALANCE_HTML = (FIXTURES_DIR / "balance_page.html").read_text(encoding="utf-8")


def test_extract_auth_token_returns_token() -> None:
    """The login parser should read the bearer token from the payload."""
    payload = {"data": {"token": "token-123"}}

    assert extract_auth_token(payload) == "token-123"


def test_extract_auth_token_raises_auth_error_for_internal_code() -> None:
    """The login parser should map upstream auth failures to the generic message."""
    with pytest.raises(MyEdenredPtAuthError):
        extract_auth_token({"internalCode": "AUTH-001", "message": ["invalid"]})


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
async def test_async_fetch_cards_retries_after_auth_error() -> None:
    """Expired sessions should trigger one fresh login and then retry."""
    expected = MyEdenredDashboardData(
        cards=(
            MyEdenredCardBalance(
                key="api_101",
                card_id="101",
                masked_card_number="**** 3456",
                card_status="ACTIVE",
                balance=Decimal("12.74"),
                balance_raw="12,74",
                data_source="api",
            ),
        )
    )
    client = MyEdenredPtClient(object(), "user@example.com", "secret")
    client._token = "expired-token"
    client._async_login = AsyncMock()
    client._async_fetch_cards_via_api = AsyncMock(
        side_effect=[MyEdenredPtAuthError("expired"), expected]
    )

    result = await client.async_fetch_cards()

    assert result == expected
    client._async_login.assert_awaited_once()
    assert client._async_fetch_cards_via_api.await_count == 2


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
    client = MyEdenredPtClient(object(), "user@example.com", "secret")
    client._async_login = AsyncMock()
    client._async_fetch_cards_via_api = AsyncMock(
        side_effect=MyEdenredPtParseError("bad payload")
    )
    client._async_fetch_cards_via_html = AsyncMock(return_value=expected)

    result = await client.async_fetch_cards()

    assert result == expected
    client._async_login.assert_awaited_once()
    client._async_fetch_cards_via_html.assert_awaited_once()
