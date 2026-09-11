#!/usr/bin/env bash
# Audeze Maxwell Battery Tray — universal installer.
# Detects the distro package manager, installs the runtime deps, sets up
# the udev rule, and installs the app + autostart for your user.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
U="$(id -un)"          # user name (for udev GROUP + autostart paths)
G="$(id -gn)"          # primary group
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null; then
        echo "Please run with root, or install sudo." >&2; exit 1
    fi
    SUDO="sudo"
fi

# ---- 1) detect package manager ----
PM=""
for c in apt-get dnf pacman zypper; do command -v "$c" >/dev/null 2>&1 && PM="$c" && break; done
if [ -z "$PM" ]; then
    echo "Unsupported system (no apt/dnf/pacman/zypper). Install deps manually:"
    echo "  python3, python3-gi (pygobject), GTK3 typelib, an AppIndicator typelib, python3-Pillow"
    exit 1
fi
echo "==> Detected package manager: $PM"

install_deps() {
  case "$PM" in
    apt-get)
      $SUDO apt-get update -y
      $SUDO apt-get install -y python3 python3-gi gir1.2-gtk-3.0 \
           gir1.2-appindicator3-0.1 gir1.2-ayatanaappindicator3-0.1 python3-pil \
        || { echo "Some apt packages missing — install them manually (see README)."; }
      ;;
    dnf)
      $SUDO dnf install -y python3-gobject gtk3 \
           libappindicator-gtk3 libayatana-appindicator-gtk3 python3-pillow \
        || { echo "Some dnf packages missing — install them manually (see README)."; }
      ;;
    pacman)
      $SUDO pacman -Sy --needed --noconfirm python-gobject gtk3 \
           libayatana-appindicator python-pillow
      ;;
    zypper)
      $SUDO zypper --non-interactive install python3-gobject \
           typelib-1_0-Gtk-3_0 python3-Pillow \
        || { echo "Some zypper packages missing — install them manually (see README)."; }
      $SUDO zypper --non-interactive install typelib-1_0-AppIndicator3-0_1 \
        || $SUDO zypper --non-interactive install typelib-1_0-AyatanaAppIndicator3-0_1
      ;;
  esac
}
install_deps

# ---- 2) udev rule (grants the Audeze dongle hidraw access) ----
echo "==> Installing udev rule (root)"
RULE="/etc/udev/rules.d/50-audeze.rules"
printf 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3329", MODE="0660", GROUP="%s", TAG+="uaccess"\n' "$G" \
  | $SUDO tee "$RULE" >/dev/null
$SUDO udevadm control --reload-rules
$SUDO udevadm trigger --subsystem-match=hidraw --subsystem-match=usb
echo "    udev rule installed: $RULE"

# ---- 3) install app + autostart for this user ----
echo "==> Installing app + autostart"
mkdir -p "$HOME/.local/bin" "$HOME/.config/autostart"
install -m755 "$DIR/audeze_battery_tray.py" "$HOME/.local/bin/audeze_battery_tray.py"
install -m644 "$DIR/audeze-battery-tray.desktop" "$HOME/.config/autostart/audeze-battery-tray.desktop"

echo
echo "Done! Start now with:"
echo "    $HOME/.local/bin/audeze_battery_tray.py"
echo "It will also auto-start on your next login."
