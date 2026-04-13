"""Unit tests for the MyEdenred Portugal sensor helpers."""

from datetime import datetime, timezone
from decimal import Decimal

from custom_components.myedenred_pt.client import MyEdenredCardBalance
from custom_components.myedenred_pt.presentation import build_balance_attributes


def test_build_balance_attributes_includes_expected_metadata() -> None:
    """The balance sensor should expose only the balance metadata needed in HA."""
    data = MyEdenredCardBalance(
        key="api_101",
        card_id="101",
        masked_card_number="**** 3456",
        card_status="ACTIVE",
        balance=Decimal("12.74"),
        balance_raw="12,74",
        data_source="api",
    )

    attributes = build_balance_attributes(
        data,
        datetime(2026, 4, 13, 14, 31, 47, tzinfo=timezone.utc),
    )

    assert attributes["balance_text"] == "12,74"
    assert attributes["masked_card_number"] == "**** 3456"
    assert attributes["card_status"] == "ACTIVE"
    assert attributes["data_source"] == "api"
    assert attributes["last_refresh"] == "2026-04-13T14:31:47+00:00"
