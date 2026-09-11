#!/usr/bin/env python3
"""Audeze Maxwell battery tray icon — KDE Plasma.

Polls the Maxwell USB dongle's battery over /dev/hidraw (Airoha "Race"
protocol) and shows the battery percentage as a coloured icon in the system
tray. Works without Wine.

Battery is reported as a coarse 0-4 scale -> shown as 0/25/50/75/100%.

Text colour is configurable with the AUDEZE_TRAY_COLOR env var (hex, e.g.
AUDEZE_TRAY_COLOR=#7CFC00). A dark outline is always drawn so the number
stays readable on light or dark trays.
"""
import os
import sys
import time
import glob
import struct
import fcntl

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
gi.require_version("AppIndicator3", "0.1")
from gi.repository import AppIndicator3 as AppIndicator

# ---------- hidraw / Race protocol ----------
VID = 0x3329          # Audeze LLC
PID = 0x4b29          # Maxwell Dongle
OUT_REPORT_ID = 0x06  # host -> dongle
IN_REPORT_ID  = 0x07  # dongle -> host
REPORT_LEN = 62       # report id + 61-byte payload

# GET_BATTERY race packet: head=05 type=5A len=2 cmd=0x0CD6
BATTERY_RACE = bytes([0x05, 0x5A, 0x02, 0x00, 0xD6, 0x0C])

# ioctl numbers (linux/hidraw.h)
#   HIDIOCGRAWINFO = _IOR('H', 0x03, struct hidraw_devinfo)
#   HIDIOCGINPUT   = _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x0A, len)
_IOC_NRSHIFT, _IOC_TYPESHIFT, _IOC_SIZESHIFT, _IOC_DIRSHIFT = 0, 8, 16, 30
_IOC_READ, _IOC_WRITE = 2, 1
def _ioc(direction, type_, nr, size):
    return (direction << _IOC_DIRSHIFT) | (ord(type_) << _IOC_TYPESHIFT) \
           | (nr << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT)

HIDIOCGRAWINFO = _ioc(_IOC_READ, "H", 0x03, 8)
def HIDIOCGINPUT(n):
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x0A, n)


# ---------- tray icon colour ----------
DEFAULT_TEXT_COLOR = (30, 215, 96)     # bright green
OUTLINE_COLOR = (0, 0, 0)
def text_color():
    hexs = os.environ.get("AUDEZE_TRAY_COLOR", "").strip().lstrip("#")
    if len(hexs) == 6:
        try:
            return tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return DEFAULT_TEXT_COLOR


def find_dongle():
    """Return an open O_RDWR fd for the Maxwell hidraw node, or None."""
    for path in glob.glob("/dev/hidraw*"):
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            info = bytearray(8)
            fcntl.ioctl(fd, HIDIOCGRAWINFO, info)
            bustype, vendor, product = struct.unpack("<Ihh", info)
            if vendor == VID and product == PID:
                return fd
        except OSError:
            pass
        os.close(fd)
    return None


def _send(fd, race):
    buf = bytearray(REPORT_LEN)
    buf[0] = OUT_REPORT_ID
    buf[1] = len(race) & 0xFF
    buf[2] = (len(race) >> 8) & 0xFF
    buf[3:3 + len(race)] = race
    os.write(fd, bytes(buf))


def _read_input_report(fd):
    """GET_REPORT for input report 0x07 via HIDIOCGINPUT. Returns bytes or b''."""
    buf = bytearray(REPORT_LEN)
    buf[0] = IN_REPORT_ID
    try:
        fcntl.ioctl(fd, HIDIOCGINPUT(REPORT_LEN), buf)
    except OSError:
        return b""
    data = bytes(buf)
    if len(data) < 3 or data[0] != IN_REPORT_ID:
        return b""
    inner_len = data[1] | (data[2] << 8)
    if inner_len == 0:
        return b""
    return data[3:3 + inner_len]


def get_battery_level(fd, attempts=5, timeout_per=0.35):
    """Return battery level 0-4, or None if unreachable."""
    for _ in range(attempts):
        try:
            _send(fd, BATTERY_RACE)
            deadline = time.monotonic() + timeout_per * attempts
            while time.monotonic() < deadline:
                data = _read_input_report(fd)
                off = 0
                while off + 6 <= len(data):
                    pkt = data[off:]
                    if pkt[0] != 0x05:
                        break
                    ptype = pkt[1]
                    plen = pkt[2] | (pkt[3] << 8)
                    cmd = pkt[4] | (pkt[5] << 8)
                    payload = pkt[6:6 + plen - 2]
                    if ptype == 0x5B and cmd == 0x0CD6 and payload:
                        return payload[0] & 0xFF
                    if plen < 2:
                        break
                    off += 6 + (plen - 2)
                time.sleep(0.05)
        except OSError:
            return None
    return None


LEVEL_PCT = {0: 0, 1: 25, 2: 50, 3: 75, 4: 100}
_UNKNOWN = "🔋 --"

# ---------- icon rendering (PIL) ----------
from PIL import Image, ImageDraw, ImageFont
FONT_PATH = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"
ICON_DIR = os.path.expanduser("~/.cache/audeze-battery")
ICON_PATH = os.path.join(ICON_DIR, "audeze_battery.png")


def _render_icon(text, path, fg, font_size=34):
    font = ImageFont.truetype(FONT_PATH, font_size)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = probe.textbbox((0, 0), text, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = 4
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - bb[0], pad - bb[1]), text, font=font,
           fill=fg + (255,), stroke_width=2, stroke_fill=OUTLINE_COLOR + (255,))
    img.save(path)


class Tray(object):
    def __init__(self):
        os.makedirs(ICON_DIR, exist_ok=True)
        self.fg = text_color()

        self.ind = AppIndicator.Indicator.new(
            "audeze-maxwell-battery", "",
            AppIndicator.IndicatorCategory.HARDWARE,
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_icon_theme_path(ICON_DIR)

        menu = Gtk.Menu()
        self.item_label = Gtk.MenuItem(label="Audeze Maxwell")
        self.item_label.set_sensitive(False)
        menu.append(self.item_label)
        refresh = Gtk.MenuItem(label="Refresh")
        refresh.connect("activate", self._on_refresh)
        menu.append(refresh)
        menu.append(Gtk.SeparatorMenuItem())
        quit_ = Gtk.MenuItem(label="Quit")
        quit_.connect("activate", Gtk.main_quit)
        menu.append(quit_)
        menu.show_all()
        self.ind.set_menu(menu)

        GLib.timeout_add_seconds(300, self._tick)
        self._update()

    def _tick(self):
        self._update()
        return True

    def _on_refresh(self, _w):
        self._update()

    def _update(self):
        fd = find_dongle()
        if fd is None:
            text = "?"; self.item_label.set_label("Audeze Maxwell — dongle not found")
        else:
            try:
                lvl = get_battery_level(fd)
            finally:
                os.close(fd)
            if lvl is not None:
                pct = LEVEL_PCT.get(lvl, lvl * 25)
                text = f"{pct}%"
                self.item_label.set_label(f"Audeze Maxwell — {pct}%")
            else:
                text = "?"
                self.item_label.set_label("Audeze Maxwell — no battery data (headset off?)")
        _render_icon(text, ICON_PATH, self.fg)
        self.ind.set_icon_full(ICON_PATH, "Audeze Maxwell battery")


def main():
    Tray()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
