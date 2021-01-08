import asuscharge
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from asuscharge_gtk._version import __version__
from dbus_next import BusType, DBusError
from dbus_next.glib import MessageBus
from dbus_next.constants import BusType
from gi.repository import Gdk, Gtk, Gio, GObject
from os.path import abspath, dirname, join
from platform import system, release
from sys import argv, exit


_MIN_KERNEL_VERSION = "5.4"
_ASUS_MODULE_NAME = "asus_nb_wmi"
_CURRENT_PATH = abspath(dirname(__file__))
_VERSION = (
    f"{asuscharge.__name__} v{asuscharge.__version__}\n" f"{__name__} v{__version__}"
)

TObject = GObject.Object


class Application(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="ca.cforrester.asuscharge-gtk",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        err = None
        if not asuscharge.supported_platform():
            err = f"Unsupported platform: {system()}.\n{argv[0]} only runs on Linux systems."
        elif not asuscharge.supported_kernel():
            err = f"Unsupported kernel version: {release()}\n{argv[0]} requires a kernel version >= {_MIN_KERNEL_VERSION}"
        elif not asuscharge.module_loaded():
            err = f"Module not loaded: the '{_ASUS_MODULE_NAME}' kernel module must be running."
        if err:
            dialog = Gtk.MessageDialog(
                flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                message_format=err,
            )
            dialog.run()
            exit()
        self.controller = asuscharge.ChargeThresholdController()
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(_CURRENT_PATH, "main.glade"))
        self.builder.connect_signals(self)
        self.css = Gtk.CssProvider()
        self.css.load_from_path(join(_CURRENT_PATH, "main.css"))
        main_window: Gtk.Window = self.builder.get_object("MainWindow")
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
            error_dialog: Gtk.Dialog = self.builder.get_object("DBusErrorDialog")
            error_dialog.connect("close", self.onMainDestroy)
            error_close_button: Gtk.Button = self.builder.get_object("ErrorCloseButton")
            error_close_button.connect("clicked", self.onMainDestroy)
            exception_text_buf: Gtk.TextBuffer = self.builder.get_object(
                "ExceptionBuffer"
            )
            exception_text_buf.set_text(str(e))
            error_dialog.present()
        else:
            reboot_persist_checkbox: Gtk.CheckButton = self.builder.get_object(
                "RebootPersistCheckbox"
            )
            reboot_persist_checkbox.set_active(
                bool(self.interface.get_persist_between_reboots_sync())
            )
            # Used to dynamically show/hide the label as the scale moves.
            self.warning_label: Gtk.Label = self.builder.get_object("WarningLabel")

            self.charge_scale: Gtk.Scale = self.builder.get_object("ChargeScale")
            self.charge_scale.connect(
                "format-value", lambda scale, value, user_data=None: f"{int(value)}%"
            )
            self.charge_scale.add_mark(100.0, Gtk.PositionType.RIGHT)
            self.charge_scale.add_mark(90.0, Gtk.PositionType.RIGHT)
            self.charge_scale.add_mark(80.0, Gtk.PositionType.RIGHT)
            self.charge_scale.add_mark(70.0, Gtk.PositionType.RIGHT)
            self.charge_scale.add_mark(60.0, Gtk.PositionType.RIGHT)
            self.charge_scale.get_style_context().add_provider_for_screen(
                Gdk.Screen.get_default(),
                self.css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            self.scale_con: Gtk.StyleContext = self.charge_scale.get_style_context()

            self.update_threshold()
            main_window.present()

    def onMainDestroy(self, user_data) -> None:
        Gtk.main_quit()

    def RebootPersistCheckbox_toggled_cb(self, checkbutton: Gtk.CheckButton) -> None:
        self.interface.set_persist_between_reboots_sync(bool(checkbutton.get_active()))

    def AboutButton_clicked_cb(self, button: Gtk.Button) -> None:
        about_window: Gtk.AboutDialog = self.builder.get_object("AboutWindow")
        about_window.set_version(_VERSION)
        about_window.run()
        about_window.hide()

    def ChargeScale_value_changed_cb(self, scale: Gtk.Scale) -> None:
        if not (value := int(scale.get_value())) in (60, 80, 100):
            self.warning_label.set_visible(visible=True)
        else:
            self.warning_label.set_visible(visible=False)
        self.set_scale_colour()
        self.interface.set_charge_end_threshold_sync(value)

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

    def update_threshold(self) -> None:
        charge_adj: Gtk.Adjustment = self.builder.get_object("ChargeAdjustment")
        charge_adj.set_value(self.controller.end_threshold)
        self.set_scale_colour()

    def set_scale_colour(self) -> None:
        if (val := self.charge_scale.get_value()) > 90:
            self.scale_con.remove_class("mid")
            self.scale_con.add_class("high")
        elif val > 80:
            self.scale_con.remove_class("high")
            self.scale_con.add_class("mid")
        else:
            self.scale_con.remove_class("mid")
            self.scale_con.remove_class("high")

    def AddScheduleButton_clicked_cb(self, button: Gtk.Button):
        add_dialog: Gtk.Dialog = self.builder.get_object("AddScheduleItemDialog")
        cancel_button: Gtk.Button = self.builder.get_object("CancelAddButton")
        response = add_dialog.run()
        print(response)
        add_dialog.hide()


if __name__ == "__main__":
    app = Application()
    Gtk.main()
