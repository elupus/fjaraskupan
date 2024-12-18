"""Device communication library."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, replace
import logging
from typing import Any, AsyncIterator
from uuid import UUID

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

COMMAND_FORMAT_FAN_SPEED_FORMAT = "-Luft-{:01d}-"
COMMAND_FORMAT_DIM = "-Dim{:03d}-"
COMMAND_FORMAT_PERIODIC_VENTING = "Period{:02d}"
COMMAND_FORMAT_AFTERCOOKINGSTRENGTHMANUAL = "Nachla-{:01d}"

COMMAND_STOP_FAN = "Luft-Aus"
COMMAND_LIGHT_ON_OFF = "Kochfeld"
COMMAND_RESETGREASEFILTER = "ResFett-"
COMMAND_RESETCHARCOALFILTER = "ResKohle"
COMMAND_AFTERCOOKINGTIMERMANUAL = "Nachlauf"
COMMAND_AFTERCOOKINGTIMERAUTO = "NachlAut"
COMMAND_AFTERCOOKINGTIMEROFF = "NachlAus"
COMMAND_ACTIVATECARBONFILTER = "coal-ava"

_LOGGER = logging.getLogger(__name__)

UUID_SERVICE = UUID("{77a2bd49-1e5a-4961-bba1-21f34fa4bc7b}")
UUID_RX = UUID("{23123e0a-1ad6-43a6-96ac-06f57995330d}")
UUID_TX = UUID("{68ecc82c-928d-4af0-aa60-0d578ffb35f7}")
UUID_CONFIG = UUID("{3e06fdc2-f432-404f-b321-dfa909f5c12c}")

DEVICE_NAME = "COOKERHOOD_FJAR"
ANNOUNCE_PREFIX = b"HOODFJAR"
ANNOUNCE_MANUFACTURER = int.from_bytes(ANNOUNCE_PREFIX[0:2], "little")

class FjaraskupanError(Exception):
    pass

class FjaraskupanBleakError(FjaraskupanError):
    pass

class FjaraskupanConnectionError(FjaraskupanBleakError):
    pass

class FjaraskupanWriteError(FjaraskupanBleakError):
    pass

class FjaraskupanReadError(FjaraskupanBleakError):
    pass

class FjaraskupanTimeout(FjaraskupanError, TimeoutError):
    pass


@dataclass(frozen=True)
class State:
    """Data received from characteristics."""

    light_on: bool = False
    after_cooking_fan_speed: int = 0
    after_cooking_on: bool = False
    carbon_filter_available: bool = False
    fan_speed: int = 0
    grease_filter_full: bool = False
    carbon_filter_full: bool = False
    dim_level: int = 0
    periodic_venting: int = 0
    periodic_venting_on: bool = False
    rssi: int = 0

    def replace_from_tx_char(self, databytes: bytes, **changes: Any):
        """Update state based on tx characteristics."""
        data = databytes.decode("ASCII")
        return replace(
            self,
            fan_speed=int(data[4]),
            light_on=data[5] == "L",
            after_cooking_on=data[6] == "N",
            carbon_filter_available=data[7] == "C",
            grease_filter_full=data[8] == "F",
            carbon_filter_full=data[9] == "K",
            dim_level=_range_check_dim(int(data[10:13]), self.dim_level),
            periodic_venting=_range_check_period(
                int(data[13:15]), self.periodic_venting
            ),
            **changes
        )

    def replace_from_manufacture_data(self, data: bytes, **changes: Any):
        """Update state based on broadcasted data."""
        light_on = _bittest(data[10], 0)
        dim_level = _range_check_dim(data[13], self.dim_level)
        if light_on and not self.light_on and dim_level < self.dim_level:
            light_on = False

        return replace(
            self,
            fan_speed=int(data[8]),
            after_cooking_fan_speed=int(data[9]),
            light_on=light_on,
            after_cooking_on=_bittest(data[10], 1),
            periodic_venting_on=_bittest(data[10], 2),
            grease_filter_full=_bittest(data[11], 0),
            carbon_filter_full=_bittest(data[11], 1),
            carbon_filter_available=_bittest(data[11], 2),
            dim_level=dim_level,
            periodic_venting=_range_check_period(data[14], self.periodic_venting),
            **changes
        )


def _range_check_dim(value: int, fallback: int):
    if value >= 0 and value <= 100:
        return value
    else:
        return fallback


def _range_check_period(value: int, fallback: int):
    if value >= 0 and value < 60:
        return value
    else:
        return fallback


def _bittest(data: int, bit: int):
    return (data & (1 << bit)) != 0


def device_filter(device: BLEDevice, advertisement_data: AdvertisementData) -> bool:
    uuids = advertisement_data.service_uuids
    if str(UUID_SERVICE) in uuids:
        return True

    if device.name == DEVICE_NAME:
        return True

    manufacturer_data = advertisement_data.manufacturer_data.get(ANNOUNCE_MANUFACTURER, b'')
    if manufacturer_data.startswith(ANNOUNCE_PREFIX[2:]):
        return True

    return False


class Device:
    """Communication handler."""


    def __init__(self, address: str, keycode=b"1234", disconnect_delay: float = 5.0) -> None:
        """Initialize handler."""
        self.address = address
        self._keycode = keycode
        self.state = State()
        self._lock = asyncio.Lock()
        self._client: BleakClient | None = None
        self._client_count = 0
        self._client_stack = AsyncExitStack()
        self._disconnect_delay = disconnect_delay
        self._disconnect_task: asyncio.Task | None = None

    async def _disconnect_callback(self):
        await asyncio.sleep(self._disconnect_delay)
        async with self._lock:
            await self._disconnect()

    async def _disconnect_later(self):
        self._disconnect_task = asyncio.create_task(self._disconnect_callback(), name="Fjaraskupen Disconnector")
        
    async def _disconnect(self):
        assert self._client
        self._client = None

        _LOGGER.debug("Disconnecting")
        try:
            await self._client_stack.pop_all().aclose()
        except TimeoutError as exc:
            _LOGGER.debug("Timeout on disconnect", exc_info=True)
            raise FjaraskupanTimeout("Timeout on disconnect") from exc
        except BleakError as exc:
            _LOGGER.debug("Error on disconnect", exc_info=True)
            raise FjaraskupanConnectionError("Error on disconnect") from exc
        _LOGGER.debug("Disconnected")

    async def _connect(self, address_or_ble_device: BLEDevice | str):
        if address_or_ble_device is None:
            address_or_ble_device = self.address

        assert self._client is None

        _LOGGER.debug("Connecting")
        try:
            self._client = await self._client_stack.enter_async_context(BleakClient(address_or_ble_device))
        except asyncio.TimeoutError as exc:
            _LOGGER.debug("Timeout on connect", exc_info=True)
            raise FjaraskupanTimeout("Timeout on connect") from exc
        except BleakError as exc:
            _LOGGER.debug("Error on connect", exc_info=True)
            raise FjaraskupanConnectionError("Error on connect") from exc
        _LOGGER.debug("Connected")
    
    @asynccontextmanager
    async def connect(self, address_or_ble_device: BLEDevice | str | None = None) -> AsyncIterator[Device]:
        async with self._lock:
            if self._disconnect_task:
                self._disconnect_task.cancel()
                self._disconnect_task = None

            if self._client is None:
                await self._connect(address_or_ble_device)
            else:
                _LOGGER.debug("Connection reused")
            self._client_count += 1

        try:
            yield self
        finally:
            async with self._lock:
                self._client_count -= 1
                if self._client_count == 0:
                    if self._disconnect_delay:
                        await self._disconnect_later()
                    else:
                        await self._disconnect()


    def characteristic_callback(self, data: bytearray):
        """Handle callback on characteristic change."""
        _LOGGER.debug("Characteristic callback: %s", data)

        if data[0:4] != self._keycode:
            _LOGGER.warning("Wrong keycode in data %s", data)
            return

        self.state = self.state.replace_from_tx_char(data)

        _LOGGER.debug("Characteristic callback result: %s", self.state)

    def detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Handle scanner data."""
        data = advertisement_data.manufacturer_data.get(ANNOUNCE_MANUFACTURER)
        if data is None:
            return
        # Recover full manufacturer data. It's breaking standard by
        # not providing a manufacturer prefix here.
        data = ANNOUNCE_PREFIX[0:2] + data
        self.detection_callback_raw(data, advertisement_data.rssi)

    def detection_callback_raw(self, data: bytes, rssi: int):

        if data[0:8] != ANNOUNCE_PREFIX:
            _LOGGER.debug("Missing key in manufacturer data %s", data)
            return

        self.state = self.state.replace_from_manufacture_data(data, rssi=rssi)

        _LOGGER.debug("Detection callback result: %s", self.state)

    async def update(self):
        async with self._lock:
            await self._update()

    async def _update(self):
        """Update internal state."""
        assert self._client, "Device must be connected"
        try:
            databytes = await self._client.read_gatt_char(UUID_RX)
        except asyncio.TimeoutError as exc:
            _LOGGER.debug("Timeout on update", exc_info=True)
            raise FjaraskupanTimeout from exc
        except BleakError as exc:
            _LOGGER.debug("Failed to update", exc_info=True)
            raise FjaraskupanReadError("Failed to update device") from exc

        self.characteristic_callback(databytes)

    async def send_command(self, cmd: str):
        """Send given command."""
        async with self._lock:
            await self._send_command(cmd)

    async def _send_command(self, cmd: str):
        """Send given command."""
        assert len(cmd) == 8
        assert self._client, "Device must be connected"
        data = self._keycode + cmd.encode("ASCII")
        try:
            await self._client.write_gatt_char(UUID_RX, data, True)
        except asyncio.TimeoutError as exc:
            _LOGGER.debug("Timeout on write", exc_info=True)
            raise FjaraskupanTimeout from exc
        except BleakError as exc:
            _LOGGER.debug("Failed to write", exc_info=True)
            raise FjaraskupanWriteError("Failed to write") from exc

        if cmd == COMMAND_STOP_FAN:
            self.state = replace(self.state, fan_speed=0)
        elif cmd == COMMAND_LIGHT_ON_OFF:
            self.state = replace(self.state, light_on=not self.state.light_on)
        elif cmd == COMMAND_AFTERCOOKINGTIMERMANUAL:
            self.state = replace(self.state, after_cooking_on=True)
        elif cmd == COMMAND_AFTERCOOKINGTIMERAUTO:
            self.state = replace(
                self.state, after_cooking_on=True, after_cooking_fan_speed=0
            )

    async def send_fan_speed(self, speed: int):
        """Set numbered fan speed."""
        async with self._lock:
            await self._send_command(COMMAND_FORMAT_FAN_SPEED_FORMAT.format(speed))
            self.state = replace(self.state, fan_speed=speed)

    async def send_after_cooking(self, speed: int):
        """Set numbered fan speed."""
        async with self._lock:
            await self._send_command(COMMAND_FORMAT_AFTERCOOKINGSTRENGTHMANUAL.format(speed))
            self.state = replace(self.state, after_cooking_fan_speed=speed)

    async def send_periodic_venting(self, minutes: int):
        """Set periodic venting."""
        async with self._lock:
            await self._send_command(COMMAND_FORMAT_PERIODIC_VENTING.format(minutes))
            self.state = replace(self.state, periodic_venting=minutes)

    async def send_dim(self, level: int):
        """Ask to dim to a certain level."""
        async with self._lock:
            if self.state.light_on ^ (level > 0):
                await self._send_command(COMMAND_LIGHT_ON_OFF)
            await self._send_command(COMMAND_FORMAT_DIM.format(level))
            self.state = replace(self.state, dim_level=level, light_on=level > 0)
