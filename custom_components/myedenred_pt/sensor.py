"""Sensor platform for MyEdenred Portugal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyEdenredPtRuntimeData
from .client import MyEdenredCardBalance
from .const import DOMAIN, PORTAL_CARDS_URL, SENSOR_KEY_AVAILABLE_BALANCE
from .coordinator import MyEdenredPtDataUpdateCoordinator
from .presentation import build_balance_attributes


async def async_setup_entry(
    hass,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    runtime_data: MyEdenredPtRuntimeData = entry.runtime_data
    async_add_entities(
        [
            MyEdenredAvailableBalanceSensor(runtime_data.coordinator, entry, card.key)
            for card in runtime_data.coordinator.data.cards
        ]
    )


class MyEdenredBaseEntity(
    CoordinatorEntity[MyEdenredPtDataUpdateCoordinator],
    SensorEntity,
):
    """Base entity shared by MyEdenred Portugal sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyEdenredPtDataUpdateCoordinator,
        entry: ConfigEntry,
        card_key: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._card_key = card_key
        self._entry_unique_id = entry.unique_id or entry.entry_id

    @property
    def card(self) -> MyEdenredCardBalance:
        """Return the current card data from the coordinator."""
        return self.coordinator.data.get_card(self._card_key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_unique_id}_{self._card_key}")},
            manufacturer="Edenred",
            model="Portugal Consumer Portal",
            name=f"MyEdenred card {self.card.masked_card_number}",
            configuration_url=PORTAL_CARDS_URL,
        )


class MyEdenredAvailableBalanceSensor(MyEdenredBaseEntity):
    """Balance sensor for a MyEdenred card."""

    _attr_icon = "mdi:wallet"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_translation_key = SENSOR_KEY_AVAILABLE_BALANCE

    def __init__(
        self,
        coordinator: MyEdenredPtDataUpdateCoordinator,
        entry: ConfigEntry,
        card_key: str,
    ) -> None:
        """Initialize the balance sensor."""
        super().__init__(coordinator, entry, card_key)
        normalized_key = card_key.replace(":", "_")
        self._attr_unique_id = (
            f"{self._entry_unique_id}_{normalized_key}_{SENSOR_KEY_AVAILABLE_BALANCE}"
        )

    @property
    def native_value(self):
        """Return the current balance."""
        return self.card.balance

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional metadata for the card."""
        return build_balance_attributes(
            self.card,
            getattr(self.coordinator, "last_update_success_time", None),
        )
