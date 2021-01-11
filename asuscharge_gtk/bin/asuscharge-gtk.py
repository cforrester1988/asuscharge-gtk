__version__ = "1.0.0"

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import asuscharge

from datetime import datetime
from dbus_next import BusType, DBusError
from dbus_next.glib import MessageBus
from dbus_next.constants import BusType
from gi.repository import Gdk, Gtk, Gio, GObject
from os.path import abspath, dirname, join
from platform import system, release
from sys import argv, exit


if __debug__:
    DATADIR = "/home/chris/Projects/asuscharge-gtk/asuscharge_gtk/data/"
else:
    DATADIR = "/usr/share/asuscharge-gtk/"
GLADE_FILE = "main.glade"
CSS_FILE = "main.css"
MIN_KERNEL_VERSION = "5.4"
ASUS_MODULE_NAME = "asus_nb_wmi"
VERSION = (
    f"{asuscharge.__name__} v{asuscharge.__version__}\n" f"{__name__} v{__version__}"
)

TObject = GObject.Object


class Application(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="ca.cforrester.asuscharge-gtk",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(DATADIR, GLADE_FILE))
        self.builder.connect_signals(self)
        self.css = Gtk.CssProvider()
        self.css.load_from_path(join(DATADIR, CSS_FILE))
        error_dialog: Gtk.MessageDialog = self.builder.get_object("ErrorDialog")
        error_buffer: Gtk.TextBuffer = self.builder.get_object("ErrorBuffer")
        if not asuscharge.supported_platform():
            error_dialog.format_secondary_text(f"Unsupported platform: {system()}.")
            error_buffer.set_text(f"{argv[0]} only runs on Linux systems.")
            error_dialog.run()
            quit()
        elif not asuscharge.supported_kernel():
            error_dialog.format_secondary_text(
                f"Unsupported kernel version: {release()}"
            )
            error_buffer.set_text(
                f"{argv[0]} requires a kernel version >= {MIN_KERNEL_VERSION}"
            )
            error_dialog.run()
            quit()
        elif not asuscharge.module_loaded():
            error_dialog.format_secondary_text(
                f"Module not loaded: the '{ASUS_MODULE_NAME}' kernel module must be running."
            )
            error_expander: Gtk.Expander = self.builder.get_object("ErrorExpander")
            error_expander.set_visible(False)
            error_dialog.run()
            quit()
        try:
            bus = MessageBus(bus_type=BusType.SYSTEM).connect_sync()
            introspection = bus.introspect_sync(
                "ca.cforrester.AsusCharge.Daemon", "/ca/cforrester/AsusCharge"
            )
            proxy = bus.get_proxy_object(
                "ca.cforrester.AsusCharge.Daemon",
                "/ca/cforrester/AsusCharge",
                introspection,
            )
            self.interface = proxy.get_interface("ca.cforrester.AsusCharge.Daemon")
        except DBusError as e:
            error_dialog.format_secondary_text(f"D-Bus Error: {e.type}")
            error_buffer.set_text(str(e.text))
            error_dialog.run()
            quit()
        self.controller = asuscharge.ChargeThresholdController()
        main_window: Gtk.Window = self.builder.get_object("MainWindow")
        reboot_persist_checkbox: Gtk.CheckButton = self.builder.get_object(
            "RebootPersistCheckbox"
        )
        reboot_persist_checkbox.set_active(
            bool(self.interface.get_persist_between_reboots_sync())
        )
        # Used to dynamically show/hide the label as the scale moves.
        self.warning_label: Gtk.Label = self.builder.get_object("WarningLabel")

        self.charge_scale: Gtk.Scale = self.builder.get_object("ChargeScale")
        self.style_charge_scale(self.charge_scale)
        main_window.present()

    def onMainDestroy(self, user_data) -> None:
        Gtk.main_quit()

    def style_charge_scale(self, charge_scale: Gtk.Scale):
        charge_scale.connect(
            "format-value", lambda scale, value, user_data=None: f"{int(value)}%"
        )
        charge_scale.add_mark(100.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(90.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(80.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(70.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(60.0, Gtk.PositionType.RIGHT)
        charge_scale.get_style_context().add_provider_for_screen(
            Gdk.Screen.get_default(),
            self.css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        charge_scale.set_value(self.controller.end_threshold)
        self.set_scale_colour(charge_scale)

    @staticmethod
    def escape_close(window: Gtk.Window, key: Gdk.EventKey, user_data=None) -> bool:
        if key.keyval == Gdk.KEY_Escape:
            window.destroy()
            return True
        else:
            return False

    def RebootPersistCheckbox_toggled_cb(self, checkbutton: Gtk.CheckButton) -> None:
        self.interface.set_persist_between_reboots_sync(bool(checkbutton.get_active()))

    def AboutButton_clicked_cb(self, button: Gtk.Button) -> None:
        about_window: Gtk.AboutDialog = self.builder.get_object("AboutWindow")
        about_window.set_version(VERSION)
        about_window.run()
        about_window.hide()

    def ChargeScale_value_changed_cb(self, scale: Gtk.Scale) -> None:
        if scale.get_name() == "ChargeScale":
            if not (value := int(scale.get_value())) in (60, 80, 100):
                self.warning_label.set_visible(visible=True)
            else:
                self.warning_label.set_visible(visible=False)
            self.interface.set_charge_end_threshold_sync(value)
        self.set_scale_colour(scale)

    def ScaleLabel_pressed_cb(
        self, box: Gtk.EventBox, user_data: TObject = None
    ) -> None:
        if self.builder.get_object("ChargeScale").is_sensitive():
            charge_adj: Gtk.Adjustment = self.builder.get_object("ChargeAdjustment")
            if (name := box.get_name()) == "FullCapBox":
                charge_adj.set_value(100)
            elif name == "BalancedBox":
                charge_adj.set_value(80)
            elif name == "BetterLifeBox":
                charge_adj.set_value(60)

    @staticmethod
    def set_scale_colour(scale: Gtk.Scale) -> None:
        scale_con = scale.get_style_context()
        if (val := scale.get_value()) > 90:
            scale_con.remove_class("mid")
            scale_con.add_class("high")
        elif val > 80:
            scale_con.remove_class("high")
            scale_con.add_class("mid")
        else:
            scale_con.remove_class("mid")
            scale_con.remove_class("high")

    def AddScheduleButton_clicked_cb(self, button: Gtk.Button):
        dialog_builder = Gtk.Builder()
        dialog_builder.add_objects_from_file(
            join(DATADIR, GLADE_FILE),
            (
                "AddScheduleItemDialog",
                "HourAdjustment",
                "MinuteAdjustment",
                "NewChargeAdjustment",
            ),
        )
        dialog_builder.connect_signals(self)
        add_dialog: Gtk.Window = dialog_builder.get_object("AddScheduleItemDialog")
        add_dialog.set_transient_for(button.get_toplevel())
        add_dialog.connect("key-press-event", self.escape_close)
        self.style_charge_scale(dialog_builder.get_object("NewChargeScale"))
        once_hour_spin: Gtk.SpinButton = dialog_builder.get_object("OnceHourSpin")
        once_hour_spin.connect("output", self.format_time_spin)
        once_hour_spin.get_adjustment().set_value(float(datetime.now().hour))
        once_min_spin: Gtk.SpinButton = dialog_builder.get_object("OnceMinuteSpin")
        once_min_spin.connect("output", self.format_time_spin)
        once_min_spin.connect("wrapped", self.wrap_minute_spin, once_hour_spin)
        once_min_spin.get_adjustment().set_value(float(datetime.now().minute))
        once_date: Gtk.Calendar = dialog_builder.get_object("OnceDate")
        once_date.select_month(datetime.now().month - 1, datetime.now().year)
        once_date.select_day(datetime.now().day)
        once_date.mark_day(datetime.now().day)
        add_dialog.present()

    def CancelButton_clicked_cb(self, button: Gtk.Button) -> None:
        button.get_toplevel().destroy()

    @staticmethod
    def format_time_spin(spin: Gtk.SpinButton) -> bool:
        adjustment: Gtk.Adjustment = spin.get_adjustment()
        spin.set_text(f"{int(adjustment.get_value()):02d}")
        return True

    @staticmethod
    def wrap_minute_spin(spin: Gtk.SpinButton, hourspin: Gtk.SpinButton) -> None:
        if spin.get_value() == 0.0:
            hourspin.spin(Gtk.SpinType.STEP_FORWARD, 1.0)
        elif spin.get_value() == 59.0:
            hourspin.spin(Gtk.SpinType.STEP_BACKWARD, 1.0)


if __name__ == "__main__":
    app = Application()
    Gtk.main()
