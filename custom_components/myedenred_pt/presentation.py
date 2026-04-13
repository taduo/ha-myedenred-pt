"""Presentation helpers for Home Assistant entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .client import MyEdenredCardBalance


def build_balance_attributes(
    data: MyEdenredCardBalance,
    last_refresh: datetime | None = None,
) -> dict[str, Any]:
    """Build the extra state attributes for the balance sensor."""
    attributes: dict[str, Any] = {
        "balance_text": data.balance_raw,
        "masked_card_number": data.masked_card_number,
        "data_source": data.data_source,
    }

    if data.card_status:
        attributes["card_status"] = data.card_status

    if last_refresh is not None:
        attributes["last_refresh"] = last_refresh.isoformat()

    return attributes
