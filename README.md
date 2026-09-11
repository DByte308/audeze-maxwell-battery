# Audeze Maxwell Battery Tray

A KDE Plasma system-tray indicator that shows the Audeze Maxwell headset's
battery percentage, read directly from the USB dongle over `/dev/hidraw`
using the Airoha "Race" protocol — no Wine, no Audeze app required.

## What it does
- Polls the dongle battery (~every 5 min) and shows a **colourful icon** with
  the percentage (0/25/50/75/100% — the dongle reports a coarse 0–4 scale).
- Auto-starts with KDE on login.
- Click for a small menu (status, refresh, quit).

## Install

### One command (recommended)
Supports Debian/Ubuntu/Mint, Fedora/Nobara/RHEL, Arch, and openSUSE. Install
runtime deps + the udev rule + autostart:

    bash install.sh

### Manual
1. **Grant hidraw access** (needed once, requires root):

       sudo bash fix_audeze.sh

   This installs `/etc/udev/rules.d/50-audeze.rules` (grants the Audeze dongle
   `3329:4b29` hidraw access to your user) and applies it live.

2. **Install runtime deps** for your distro (python3-gi + an AppIndicator
   typelib + python3-Pillow + GTK3).

3. **Run / autostart**

       chmod +x audeze_battery_tray.py
       ./audeze_battery_tray.py            # run in foreground

   Autostart: copy `audeze-battery-tray.desktop` to `~/.config/autostart/`.

## Configuration
- Text colour: set `AUDEZE_TRAY_COLOR=#RRGGBB` (default bright green).
- Poll interval: edit `GLib.timeout_add_seconds(300, ...)` in the script.

## Requirements
- Linux + Python 3 + PyGObject (gi/Gtk) + AppIndicator3
- Pillow (PIL) and a DejaVu font for icon rendering
- The Maxwell dongle plugged in (`lsusb` shows `3329:4b29`)

## Notes
- Battery is reported as a coarse 0–4 value, so percentages go in 25% steps.
- If the headset is powered off in its case, the dongle can't report battery
  and the icon shows a grey `?`.

## License
MIT
