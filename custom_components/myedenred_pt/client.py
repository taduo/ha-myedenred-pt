"""HTTP client for the MyEdenred Portugal portal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from .const import (
    CARD_ACCOUNT_API_URL,
    CARDS_API_URL,
    LOGIN_API_URL,
    PORTAL_CARDS_URL,
    REQUEST_TIMEOUT_SECONDS,
    normalize_username,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

_AUTH_FAILURE_MESSAGE = "MyEdenred rejected the credentials provided for this account."
_BALANCE_PATTERN = re.compile(r"[-+]?\d[\d.,]*")
_TAG_PATTERN = re.compile(r"<[^>]+>")


class MyEdenredPtError(Exception):
    """Base integration error."""


class MyEdenredPtAuthError(MyEdenredPtError):
    """Raised when authentication fails."""


class MyEdenredPtConnectionError(MyEdenredPtError):
    """Raised when the website cannot be reached."""


class MyEdenredPtParseError(MyEdenredPtError):
    """Raised when the balance cannot be parsed."""


@dataclass(frozen=True)
class MyEdenredCardReference:
    """Card reference returned by the cards listing endpoint."""

    card_id: str
    masked_card_number: str
    card_status: str | None
    owner_name: str | None


@dataclass(frozen=True)
class MyEdenredCardBalance:
    """Normalized card balance data."""

    key: str
    card_id: str
    masked_card_number: str
    card_status: str | None
    balance: Decimal
    balance_raw: str
    data_source: str
    owner_name: str | None = None


@dataclass(frozen=True)
class MyEdenredDashboardData:
    """Normalized dashboard data."""

    cards: tuple[MyEdenredCardBalance, ...]

    def get_card(self, key: str) -> MyEdenredCardBalance:
        """Return a card by its stable key."""
        for card in self.cards:
            if card.key == key:
                return card
        raise KeyError(key)


def parse_decimal_value(raw_value: object) -> Decimal:
    """Parse a localized decimal value into a Decimal."""
    if isinstance(raw_value, Decimal):
        return raw_value
    if isinstance(raw_value, int):
        return Decimal(raw_value)
    if isinstance(raw_value, float):
        return Decimal(str(raw_value))

    if not isinstance(raw_value, str):
        raise MyEdenredPtParseError("Expected a numeric balance value.")

    cleaned = raw_value.replace("\xa0", " ").replace("€", "").replace(" ", "").strip()
    if not cleaned:
        raise MyEdenredPtParseError("Expected a numeric balance value, but the field was empty.")

    if "," in cleaned and "." in cleaned:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
    elif "," in cleaned:
        decimal_separator = ","
    elif "." in cleaned:
        decimal_separator = "."
    else:
        decimal_separator = None

    normalized = cleaned
    if decimal_separator is not None:
        thousands_separator = "." if decimal_separator == "," else ","
        normalized = normalized.replace(thousands_separator, "")
        normalized = normalized.replace(decimal_separator, ".")

    try:
        return Decimal(normalized)
    except InvalidOperation as err:
        raise MyEdenredPtParseError(
            f"Could not parse numeric value: {raw_value}"
        ) from err


def format_decimal_text(value: Decimal) -> str:
    """Render a Decimal as a user-friendly balance string."""
    normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(normalized, "f").replace(".", ",")


def mask_card_number(value: object) -> str:
    """Mask a card number before exposing it to Home Assistant."""
    if not isinstance(value, str):
        return "unknown"

    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        return "unknown"
    suffix = digits[-4:] if len(digits) >= 4 else digits
    return f"**** {suffix}"


def extract_auth_token(payload: object) -> str:
    """Extract the auth token from the login response."""
    if not isinstance(payload, dict):
        raise MyEdenredPtParseError("Unexpected login payload returned by MyEdenred.")

    if payload.get("internalCode") is not None:
        raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)

    data = payload.get("data")
    if not isinstance(data, dict):
        raise MyEdenredPtParseError("MyEdenred login payload did not include token data.")

    token = data.get("token")
    if not isinstance(token, str) or not token.strip():
        raise MyEdenredPtParseError("MyEdenred login payload did not include a usable token.")

    return token.strip()


def extract_card_references(payload: object) -> tuple[MyEdenredCardReference, ...]:
    """Extract card metadata from the cards list payload."""
    if not isinstance(payload, dict):
        raise MyEdenredPtParseError("Unexpected cards payload returned by MyEdenred.")

    data = payload.get("data")
    if not isinstance(data, list):
        raise MyEdenredPtParseError("MyEdenred did not return a list of cards.")

    cards: list[MyEdenredCardReference] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        card_id = item.get("id")
        if card_id is None:
            continue

        owner_name = item.get("ownerName")
        card_status = item.get("status")
        cards.append(
            MyEdenredCardReference(
                card_id=str(card_id),
                masked_card_number=mask_card_number(item.get("number")),
                card_status=card_status if isinstance(card_status, str) else None,
                owner_name=owner_name if isinstance(owner_name, str) else None,
            )
        )

    if not cards:
        raise MyEdenredPtParseError("MyEdenred did not return any cards for this account.")

    return tuple(cards)


def extract_card_balance(
    card: MyEdenredCardReference,
    payload: object,
) -> MyEdenredCardBalance:
    """Extract balance details for a single card from the account payload."""
    if not isinstance(payload, dict):
        raise MyEdenredPtParseError("Unexpected account payload returned by MyEdenred.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise MyEdenredPtParseError("MyEdenred account payload did not include data.")

    account = data.get("account", data)
    if not isinstance(account, dict):
        raise MyEdenredPtParseError("MyEdenred account payload did not include account details.")

    balance = parse_decimal_value(account.get("availableBalance"))
    holder_first_name = account.get("cardHolderFirstName")
    holder_last_name = account.get("cardHolderLastName")
    owner_name = " ".join(
        part.strip()
        for part in [holder_first_name, holder_last_name]
        if isinstance(part, str) and part.strip()
    )
    status = account.get("status") if isinstance(account.get("status"), str) else None

    return MyEdenredCardBalance(
        key=f"api_{card.card_id}",
        card_id=card.card_id,
        masked_card_number=mask_card_number(account.get("cardNumber"))
        if isinstance(account.get("cardNumber"), str)
        else card.masked_card_number,
        card_status=status or card.card_status,
        balance=balance,
        balance_raw=format_decimal_text(balance),
        data_source="api",
        owner_name=owner_name or card.owner_name,
    )


def extract_cards_from_html(html: str) -> tuple[MyEdenredCardBalance, ...]:
    """Extract card balances from the observed authenticated HTML dashboard."""
    balance_texts = _extract_class_values(html, "card-balance", required_class="autoNumeric")
    if not balance_texts:
        raise MyEdenredPtParseError(
            "Logged in successfully, but could not find the available balance element."
        )

    number_texts = _extract_class_values(html, "card-number")
    status_texts = _extract_class_values(html, "card-status")
    owner_texts = _extract_class_values(html, "card-name")

    cards: list[MyEdenredCardBalance] = []
    for index, raw_text in enumerate(balance_texts, start=1):
        match = _BALANCE_PATTERN.search(raw_text)
        if not match:
            continue

        balance_raw = match.group(0)
        balance = parse_decimal_value(balance_raw)
        card_number_text = number_texts[index - 1] if index - 1 < len(number_texts) else None
        card_status = status_texts[index - 1] if index - 1 < len(status_texts) else None
        owner_name = owner_texts[index - 1] if index - 1 < len(owner_texts) else None

        cards.append(
            MyEdenredCardBalance(
                key=f"html_{index}",
                card_id=f"html_{index}",
                masked_card_number=mask_card_number(card_number_text),
                card_status=card_status,
                balance=balance,
                balance_raw=balance_raw,
                data_source="html",
                owner_name=owner_name,
            )
        )

    if not cards:
        raise MyEdenredPtParseError(
            "Logged in successfully, but could not parse the available balance."
        )

    return tuple(cards)


def _extract_class_values(
    html: str,
    class_name: str,
    *,
    required_class: str | None = None,
) -> list[str]:
    """Extract text content from simple div-based class selectors."""
    pattern = re.compile(
        rf'<div[^>]*class="([^"]*\b{re.escape(class_name)}\b[^"]*)"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    values: list[str] = []
    for class_value, raw_inner in pattern.findall(html):
        if required_class and required_class not in class_value.split():
            continue
        text = _TAG_PATTERN.sub(" ", raw_inner).replace("\xa0", " ")
        text = " ".join(text.split())
        if text:
            values.append(text)
    return values


class MyEdenredPtClient:
    """Client for the MyEdenred Portugal website."""

    def __init__(
        self,
        session: "ClientSession",
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._username = normalize_username(username)
        self._password = password
        self._token: str | None = None

    async def async_fetch_cards(self) -> MyEdenredDashboardData:
        """Fetch balance data for all cards in the configured account."""
        for attempt in range(2):
            if self._token is None:
                await self._async_login()

            try:
                return await self._async_fetch_cards_via_api()
            except MyEdenredPtParseError as api_err:
                _LOGGER.debug(
                    "MyEdenred API parsing failed, trying HTML balance fallback: %s",
                    api_err,
                )
                try:
                    return await self._async_fetch_cards_via_html()
                except MyEdenredPtParseError:
                    raise api_err
            except MyEdenredPtAuthError:
                self._clear_auth()
                if attempt == 1:
                    raise

        raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)

    def _clear_auth(self) -> None:
        """Clear cached authentication state."""
        self._token = None

    async def _async_login(self) -> None:
        """Authenticate against the MyEdenred login endpoint."""
        status, payload = await self._async_request_json(
            "post",
            LOGIN_API_URL,
            params={"appVersion": "1.0", "appType": "PORTAL", "channel": "WEB"},
            headers={"Content-Type": "application/json"},
            json={"userId": self._username, "password": self._password},
        )

        if status in {400, 401, 403}:
            raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)
        if status != 200:
            raise MyEdenredPtConnectionError(
                f"MyEdenred login failed with HTTP status {status}."
            )

        self._token = extract_auth_token(payload)

    async def _async_fetch_cards_via_api(self) -> MyEdenredDashboardData:
        """Fetch card balances using the JSON API."""
        status, cards_payload = await self._async_request_json("get", CARDS_API_URL)
        if status in {401, 403}:
            raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)
        if status != 200:
            raise MyEdenredPtConnectionError(
                f"MyEdenred cards request failed with HTTP status {status}."
            )

        cards = extract_card_references(cards_payload)
        balances: list[MyEdenredCardBalance] = []
        for card in cards:
            detail_status, detail_payload = await self._async_request_json(
                "get",
                CARD_ACCOUNT_API_URL.format(card_id=card.card_id),
            )
            if detail_status in {401, 403}:
                raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)
            if detail_status != 200:
                raise MyEdenredPtConnectionError(
                    f"MyEdenred card detail request failed with HTTP status {detail_status}."
                )

            balances.append(extract_card_balance(card, detail_payload))

        return MyEdenredDashboardData(cards=tuple(balances))

    async def _async_fetch_cards_via_html(self) -> MyEdenredDashboardData:
        """Attempt to fetch balances from the authenticated HTML page."""
        status, html = await self._async_request_text("get", PORTAL_CARDS_URL)
        if status in {401, 403}:
            raise MyEdenredPtAuthError(_AUTH_FAILURE_MESSAGE)
        if status != 200:
            raise MyEdenredPtConnectionError(
                f"MyEdenred HTML balance request failed with HTTP status {status}."
            )

        return MyEdenredDashboardData(cards=extract_cards_from_html(html))

    async def _async_request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> tuple[int, object]:
        """Perform an HTTP request and decode the response as JSON."""
        status, text = await self._async_request_text(method, url, **kwargs)
        try:
            return status, json.loads(text)
        except json.JSONDecodeError as err:
            raise MyEdenredPtParseError(
                f"MyEdenred returned invalid JSON for {url}."
            ) from err

    async def _async_request_text(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> tuple[int, str]:
        """Perform an HTTP request and return the response body as text."""
        headers = dict(kwargs.pop("headers", {}))
        if self._token and "Authorization" not in headers:
            headers["Authorization"] = self._token

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            ) as response:
                return response.status, await response.text()
        except TimeoutError as err:
            raise MyEdenredPtConnectionError(
                "Timed out while contacting MyEdenred."
            ) from err
        except Exception as err:
            raise MyEdenredPtConnectionError(
                "Could not connect to MyEdenred."
            ) from err
