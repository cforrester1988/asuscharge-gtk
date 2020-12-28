# type: ignore
import asyncio
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from os.path import abspath, dirname, join
from os import getuid
from sys import argv, exit
from typing import Type
from platform import system, release
from gi.repository import Gdk, Gtk, Gio, GObject

from ._version import __version__

import asuscharge

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
        self.css = Gtk.CssProvider()
        self.css.load_from_path(join(_CURRENT_PATH, "main.css"))

        main_window: Gtk.Window = self.builder.get_object("MainWindow")
        main_window.connect("destroy", Gtk.main_quit)

        aboutButton: Gtk.Button = self.builder.get_object("AboutButton")
        aboutButton.connect("clicked", self.show_about)

        unlock_infobar: Gtk.InfoBar = self.builder.get_object("UnlockInfoBar")
        unlock_infobar.set_revealed(True)
        unlock_button: Gtk.Button = self.builder.get_object("UnlockButton")
        unlock_button.connect("clicked", self.unlock_button_clicked)

        charge_scale: Gtk.Scale = self.builder.get_object("ChargeScale")
        charge_scale.connect(
            "format-value", lambda scale, value, user_data=None: f"{int(value)}%"
        )
        charge_scale.add_mark(100.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(80.0, Gtk.PositionType.RIGHT)
        charge_scale.add_mark(60.0, Gtk.PositionType.RIGHT)
        charge_scale.get_style_context().add_provider_for_screen(
            Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        charge_adj: Gtk.Adjustment = self.builder.get_object("ChargeAdjustment")
        charge_adj.connect("value-changed", self.scale_moved)
        self.builder.get_object("FullCapBox").connect(
            "button-press-event", self.press_scale_label
        )
        self.builder.get_object("BalancedBox").connect(
            "button-press-event", self.press_scale_label
        )
        self.builder.get_object("BetterLifeBox").connect(
            "button-press-event", self.press_scale_label
        )

        self.update_threshold()
        main_window.present()

    def show_about(self, button: Gtk.Button) -> None:
        about_window: Gtk.AboutDialog = self.builder.get_object("AboutWindow")
        about_window.set_version(_VERSION)
        about_window.run()
        about_window.hide()

    def unlock_button_clicked(self, button: Gtk.Button) -> None:
        charge_scale: Gtk.Scale = self.builder.get_object("ChargeScale")
        unlock_infobar: Gtk.InfoBar = self.builder.get_object("UnlockInfoBar")
        scheduler_button: Gtk.Button = self.builder.get_object("SchedulerButton")
        charge_scale.set_sensitive(True)
        unlock_infobar.set_revealed(False)
        scheduler_button.set_sensitive(True)

    def set_scale_colour(self) -> None:
        charge_scale: Gtk.Scale = self.builder.get_object("ChargeScale")
        scale_con: Gtk.StyleContext = charge_scale.get_style_context()
        if (val := charge_scale.get_value()) > 90:
            scale_con.remove_class("mid")
            scale_con.add_class("high")
        elif val > 80:
            scale_con.remove_class("high")
            scale_con.add_class("mid")
        else:
            scale_con.remove_class("mid")
            scale_con.remove_class("high")

    def press_scale_label(self, box: Gtk.EventBox, user_data: TObject = None) -> None:
        if self.builder.get_object("ChargeScale").is_sensitive():
            charge_adj: Gtk.Adjustment = self.builder.get_object("ChargeAdjustment")
            if (name := box.get_name()) == "FullCapBox":
                charge_adj.set_value(100)
            elif name == "BalancedBox":
                charge_adj.set_value(80)
            elif name == "BetterLifeBox":
                charge_adj.set_value(60)

    def scale_moved(self, scale: Gtk.Scale) -> None:
        label: Gtk.Label = self.builder.get_object("WarningLabel")
        if not scale.get_value() in (60, 80, 100):
            label.set_visible(visible=True)
        else:
            label.set_visible(visible=False)
        self.set_scale_colour()

    def update_threshold(self) -> None:
        charge_adj: Gtk.Adjustment = self.builder.get_object("ChargeAdjustment")
        charge_adj.set_value(self.controller.end_threshold)
        self.set_scale_colour()


if __name__ == "__main__":
    app = Application()
    Gtk.main()
