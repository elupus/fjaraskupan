import asyncio
import argparse
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from . import device_filter

parser = argparse.ArgumentParser(description="Control kitchen fans")

subparsers = parser.add_subparsers(dest="subcommand")

parse_scan = subparsers.add_parser("scan")
parse_scan.add_argument("--timeout", default=5.0, type=float)


async def scan(args):
    async with BleakScanner() as scanner:

        async def detection(device: BLEDevice, advertisement_data: AdvertisementData):
            if device_filter(device, advertisement_data):
                print(f"Detection: {device} - {advertisement_data}")

        scanner.register_detection_callback(detection)
        await asyncio.sleep(args.timeout)


async def main():
    args = parser.parse_args()
    if args.subcommand == "scan":
        await scan(args)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
