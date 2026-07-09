"""Constants for the MyEdenred Portugal integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

DOMAIN = "myedenred_pt"
NAME = "MyEdenred Portugal"
VERSION = "0.2.0b1"

CONF_TOKEN = "token"
CONF_USERNAME = "username"
CONF_UPDATE_INTERVAL_MINUTES = "update_interval_minutes"

API_BASE_URL = "https://www.myedenred.pt/edenred-customer/v2/"
APP_VERSION = "1.0"
APP_TYPE = "PORTAL"
APP_CHANNEL = "WEB"
COMMON_API_PARAMS = {
    "appVersion": APP_VERSION,
    "appType": APP_TYPE,
    "channel": APP_CHANNEL,
}

LOGIN_API_URL = f"{API_BASE_URL}authenticate/default"
LOGIN_CHALLENGE_API_URL = f"{LOGIN_API_URL}/challenge"
LOGIN_CHALLENGE_RESEND_API_URL = f"{API_BASE_URL}authenticate/challenge/resend"
CARDS_API_URL = f"{API_BASE_URL}protected/card/list"
CARD_ACCOUNT_API_URL = f"{API_BASE_URL}protected/card/{{card_id}}/accountmovement"
PORTAL_CARDS_URL = "https://www.myedenred.pt/#myCards"

REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_UPDATE_INTERVAL_MINUTES = 30
UPDATE_INTERVAL_MINUTES_OPTIONS: tuple[int, ...] = (15, 30, 60, 120)
UPDATE_INTERVAL_OPTION_LABELS = {
    str(minutes): f"{minutes} min" for minutes in UPDATE_INTERVAL_MINUTES_OPTIONS
}

PLATFORMS: list[str] = ["sensor"]

SENSOR_KEY_AVAILABLE_BALANCE = "available_balance"


def normalize_username(value: object) -> str:
    """Normalize a username value for storage and comparison."""
    if not isinstance(value, str):
        return ""

    return value.strip().lower()


def is_valid_username(value: object) -> bool:
    """Return True when the username is not empty."""
    return bool(normalize_username(value))


def mask_identifier(value: str) -> str:
    """Mask a user identifier for UI titles."""
    normalized = normalize_username(value)
    if not normalized:
        return "account"
    if len(normalized) <= 4:
        return normalized
    return normalized[-4:]


def title_for_username(username: str) -> str:
    """Build a user-friendly config entry title."""
    return f"MyEdenred PT {mask_identifier(username)}"


def normalize_update_interval_minutes(value: object) -> int:
    """Normalize the configured update interval."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_INTERVAL_MINUTES

    if minutes not in UPDATE_INTERVAL_MINUTES_OPTIONS:
        return DEFAULT_UPDATE_INTERVAL_MINUTES

    return minutes


def get_update_interval_from_options(options: Mapping[str, object]) -> timedelta:
    """Build the polling interval from config-entry options."""
    minutes = normalize_update_interval_minutes(
        options.get(
            CONF_UPDATE_INTERVAL_MINUTES,
            DEFAULT_UPDATE_INTERVAL_MINUTES,
        )
    )
    return timedelta(minutes=minutes)


__all__ = [
    "API_BASE_URL",
    "APP_CHANNEL",
    "APP_TYPE",
    "APP_VERSION",
    "CARD_ACCOUNT_API_URL",
    "CARDS_API_URL",
    "COMMON_API_PARAMS",
    "CONF_TOKEN",
    "CONF_UPDATE_INTERVAL_MINUTES",
    "CONF_USERNAME",
    "DEFAULT_UPDATE_INTERVAL_MINUTES",
    "DOMAIN",
    "LOGIN_API_URL",
    "LOGIN_CHALLENGE_API_URL",
    "LOGIN_CHALLENGE_RESEND_API_URL",
    "NAME",
    "PLATFORMS",
    "PORTAL_CARDS_URL",
    "REQUEST_TIMEOUT_SECONDS",
    "SENSOR_KEY_AVAILABLE_BALANCE",
    "UPDATE_INTERVAL_OPTION_LABELS",
    "VERSION",
    "get_update_interval_from_options",
    "is_valid_username",
    "normalize_update_interval_minutes",
    "normalize_username",
    "title_for_username",
]
