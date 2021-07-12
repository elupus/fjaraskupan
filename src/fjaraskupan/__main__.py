import asyncio
import argparse
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from . import COMMAND_LIGHT_ON_OFF, Device, device_filter

parser = argparse.ArgumentParser(description="Control kitchen fans")

subparsers = parser.add_subparsers(dest="subcommand")

parse_scan = subparsers.add_parser("scan")
parse_scan.add_argument("--timeout", default=5.0, type=float)

parse_state = subparsers.add_parser("state")
parse_state.add_argument("device", type=str)

parse_light = subparsers.add_parser("light")
parse_light.add_argument("device", type=str)
parse_light.add_argument("level", type=int)

parse_fan = subparsers.add_parser("fan")
parse_fan.add_argument("device", type=str)
parse_fan.add_argument("speed", type=int)

parse_command = subparsers.add_parser("command")
parse_command.add_argument("command", type=str)

async def async_scan(args):
    async with BleakScanner() as scanner:

        async def detection(device: BLEDevice, advertisement_data: AdvertisementData):
            if device_filter(device, advertisement_data):
                print(f"Detection: {device} - {advertisement_data}")

        scanner.register_detection_callback(detection)
        await asyncio.sleep(args.timeout)

async def async_light(args):
    async with Device(args.device) as device:
        await device.update()

        if args.level == 0:
            if device.state.light_on:
                await device.send_command(COMMAND_LIGHT_ON_OFF)
        else:
            if device.state.light_on is False:
                await device.send_command(COMMAND_LIGHT_ON_OFF)
                await asyncio.sleep(3)
            await device.send_dim(args.level)


async def async_fan(args):
    async with Device(args.device) as device:
        await device.send_fan_speed(args.speed)


async def async_state(args):
    async with Device(args.device) as device:
        await device.update()
        print(device.state)

async def async_command(args):
    async with Device(args.device) as device:
        await device.send_command(args.command)

async def main():
    args = parser.parse_args()
    if args.subcommand == "scan":
        await async_scan(args)
    elif args.subcommand == "light":
        await async_light(args)
    elif args.subcommand == "fan":
        await async_fan(args)
    elif args.subcommand == "state":
        await async_state(args)
    elif args.subcommand == "command":
        await async_command(args)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
