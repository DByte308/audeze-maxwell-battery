#!/usr/bin/env bash
set -e
printf 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3329", MODE="0660", GROUP="d", TAG+="uaccess"\n' | sudo tee /etc/udev/rules.d/50-audeze.rules
sudo udevadm control --reload-rules
sudo chmod 660 /dev/hidraw12
sudo chown root:d /dev/hidraw12
echo "rule installed; /dev/hidraw12 now:"
ls -l /dev/hidraw12
