thermostat-logger
=================

Logs and graphs thermostat status, temperature, and time.
Receives thermostat events (on/off) via interrupts.
Useful if you want to see how much your heating/cooling system is running.

Uses an [HCPL3700](http://www.avagotech.com/pages/en/optocouplers_plastic/isolated_voltage_current_detector/hcpl-3700/) optocoupler to generate the logic inputs for thermostat status/events; uses an [ADT7410](http://www.analog.com/en/mems-sensors/digital-temperature-sensors/adt7410/products/product.html) to measure temperature. Runs on a Raspberry Pi.

Requires hipi-i2c to be installed, since the kernel driver and python-smbus on the Pi don't play well with a number of I2C devices. hipi-i2c is part of [HiPi](http://raspberry.znix.com/p/about.html).

Configure settings in thermostat_monitor.conf before running. You'll need a Plotly account and API key if you want to use the graphing feature.

For details on building the hardware associated with this repository, see this [Instructable](http://www.instructables.com/id/Log-and-Graph-24V-Thermostat-Events-Optocoupler-Ra/).
