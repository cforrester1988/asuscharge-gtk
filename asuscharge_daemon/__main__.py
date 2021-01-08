import asuscharge
import asyncio
import configparser
import os

from sys import argv, exit


if (
    not asuscharge.supported_platform()
    or not asuscharge.supported_kernel()
    or not asuscharge.module_loaded()
):
    print(f"{argv[0]} is not supported on this system.")
    exit()

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, dbus_property, method


DBUS_NAME = "ca.cforrester.AsusCharge.Daemon"
DBUS_PATH = "/ca/cforrester/AsusCharge"
DBUS_INTERFACE = "ca.cforrester.AsusCharge.Daemon"
CONFIG_PATH = "/var/lib/asuscharge_daemon/"
CONFIG_FILE = f"{CONFIG_PATH}asuscharge_daemon.conf"
THRESHOLD_FILE = f"{CONFIG_PATH}charge_control_end_threshold"

DBus_Int = "i"
DBus_Bool = "b"


class ChargeControlService(ServiceInterface):
    def __init__(self, name: str, config: configparser.ConfigParser):
        super().__init__(name)
        self.config = config
        self.charge_controller = asuscharge.ChargeThresholdController()
        if self.config["DEFAULT"].getboolean("PersistBetweenReboots"):
            try:
                with open(THRESHOLD_FILE, "r") as f:
                    self.ChargeEndThreshold = int(f.read())
                    print(
                        f"Loaded saved charge threshold state: {self.ChargeEndThreshold}%"
                    )
                os.remove(THRESHOLD_FILE)
            except FileNotFoundError:
                pass

    @dbus_property()
    def ChargeEndThreshold(self) -> DBus_Int:
        return self.charge_controller.end_threshold

    @ChargeEndThreshold.setter
    def ChargeEndThreshold(self, value: DBus_Int) -> None:
        if self.charge_controller.end_threshold == value:
            return
        else:
            self.charge_controller.end_threshold = value
            self.emit_properties_changed(
                {"ChargeEndThreshold": self.charge_controller.end_threshold}
            )

    @dbus_property()
    def PersistBetweenReboots(self) -> DBus_Bool:
        return self.config["DEFAULT"].getboolean("PersistBetweenReboots")

    @PersistBetweenReboots.setter
    def PersistBetweenReboots(self, value: DBus_Bool) -> None:
        if value == self.config["DEFAULT"].getboolean("PersistBetweenReboots"):
            return
        elif value:
            self.config["DEFAULT"]["PersistBetweenReboots"] = "yes"
        else:
            self.config["DEFAULT"]["PersistBetweenReboots"] = "no"
        with open(CONFIG_FILE, "w") as f:
            self.config.write(f)
            f.flush()
        self.emit_properties_changed(
            {
                "PersistBetweenReboots": self.config["DEFAULT"].getboolean(
                    "PersistBetweenReboots"
                ),
            }
        )


async def main():
    config = configparser.ConfigParser()
    config["DEFAULT"]["PersistBetweenReboots"] = "yes"
    if config.read(CONFIG_FILE) == []:
        print(f"Config file not found. Generating a default config to {CONFIG_FILE}")
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    interface = ChargeControlService(DBUS_INTERFACE, config)
    bus.export(DBUS_PATH, interface)
    await bus.request_name(DBUS_NAME)
    await bus.wait_for_disconnect()
    with open(CONFIG_FILE, "w") as f:
        config.write(f)
        f.flush()


asyncio.get_event_loop().run_until_complete(main())
