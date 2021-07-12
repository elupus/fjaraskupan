********************************
Fjäråskupan Bluetooth Control
********************************
This module support controlling Fjäråskupan kitchen fans over bluetooth

Status
______

.. image:: https://github.com/elupus/fjaraskupan/actions/workflows/python-package.yml/badge.svg
    :target: https://github.com/elupus/fjaraskupan

Module
======

Code to set fan speed using library.

.. code-block:: python


    async def run():
        async with Device("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE") as device:
            await device.set_fan_speed(5)

    loop = asyncio.get_event_loop()
    loop.run_until_complete (run())



Commandline
===========

Scan for possible devices.

.. code-block:: bash

  python -m fjaraskupan scan


Code to set fan speed using commandline.

.. code-block:: bash

  python -m fjaraskupan fan AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE 5


To get help on possible commands 

.. code-block:: bash

  python -m fjaraskupan -h
  python -m fjaraskupan light -h
  python -m fjaraskupan fan -h
