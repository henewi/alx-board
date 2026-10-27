#!/bin/bash
# ALX Departures: one-time setup on a fresh Raspberry Pi OS Lite (64-bit).
#
#   1. Copy the alx folder onto the Pi (or unzip alx-departures.zip there)
#   2. cd alx && sudo bash pi/install.sh
#   3. sudo reboot
#
# Safe to run again: it updates the app and services but never touches
# /opt/alx/data (Alex's logbook, stats, settings, postcodes, config.json).
#
# Optional settings:  ALX_TZ=Europe/London  ALX_WIFI_COUNTRY=GB  sudo -E bash pi/install.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Please run with sudo: sudo bash pi/install.sh"; exit 1; }
SRC="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$SRC/server.py" ] || { echo "Run this from the alx folder (server.py not found in $SRC)"; exit 1; }
ROOT=/opt/alx
TZ_NAME="${ALX_TZ:-Europe/London}"
COUNTRY="${ALX_WIFI_COUNTRY:-GB}"
step() { echo; echo "==> $*"; }

step "Installing packages (cage + Chromium for the screen)"
apt-get update
CHROME_PKG=chromium
apt-cache show chromium >/dev/null 2>&1 || CHROME_PKG=chromium-browser
apt-get install -y --no-install-recommends cage "$CHROME_PKG" python3 network-manager ca-certificates
CHROMIUM="$(command -v chromium || command -v chromium-browser)"

step "Creating the 'alx' user that runs the screen"
id alx >/dev/null 2>&1 || useradd -m -s /bin/bash alx
usermod -aG video,render,input alx
passwd -l alx >/dev/null

step "Installing the app"
VER="$(tr -d '[:space:]' < "$SRC/VERSION" 2>/dev/null || true)"; VER="${VER:-v1.0}"
mkdir -p "$ROOT/releases" "$ROOT/data/cache" "$ROOT/bin"
DEST="$ROOT/releases/$VER"
rm -rf "$DEST.tmp"; mkdir -p "$DEST.tmp"
tar -C "$SRC" --exclude=./cache --exclude=./config.json --exclude='*/__pycache__' --exclude='*.pyc' -cf - . | tar -C "$DEST.tmp" -xf -
echo "$VER" > "$DEST.tmp/VERSION"
rm -rf "$DEST"; mv "$DEST.tmp" "$DEST"
ln -sfn "$DEST" "$ROOT/current.new" && mv -T "$ROOT/current.new" "$ROOT/current"
install -m 755 "$SRC/pi/alxctl.py" "$ROOT/bin/alxctl"
ln -sfn "$ROOT/bin/alxctl" /usr/local/bin/alxctl

# config.json lives with the data, so updates never overwrite it
if [ ! -f "$ROOT/data/config.json" ]; then
  if [ -f "$SRC/config.json" ]; then cp "$SRC/config.json" "$ROOT/data/config.json"; else echo '{}' > "$ROOT/data/config.json"; fi
fi
python3 - "$ROOT/data/config.json" <<'PY'
import json, sys
p = sys.argv[1]
cfg = json.load(open(p))
cfg["cache_dir"] = "/opt/alx/data/cache"
json.dump(cfg, open(p, "w"), indent=2)
PY
chmod 600 "$ROOT/data/config.json"     # may hold the update token

step "Installing services"
for f in "$SRC"/pi/systemd/*; do
  sed "s#@CHROMIUM@#$CHROMIUM#g" "$f" > "/etc/systemd/system/$(basename "$f")"
done
mkdir -p /etc/systemd/system.conf.d /etc/systemd/journald.conf.d
# Hardware watchdog: if the whole Pi ever locks up, it reboots itself
cat > /etc/systemd/system.conf.d/alx-watchdog.conf <<'EOF'
[Manager]
RuntimeWatchdogSec=15s
RebootWatchdogSec=2min
EOF
# Keep logs small, to spare the SD card
cat > /etc/systemd/journald.conf.d/alx.conf <<'EOF'
[Journal]
SystemMaxUse=40M
EOF
systemctl daemon-reload
systemctl disable getty@tty1.service >/dev/null 2>&1 || true
systemctl enable alx.service alx-kiosk.service alx-watchdog.timer alx-nightly.timer
systemctl set-default graphical.target

step "Wi-Fi country ($COUNTRY) and time zone ($TZ_NAME)"
command -v raspi-config >/dev/null && raspi-config nonint do_wifi_country "$COUNTRY" || true
rfkill unblock wifi 2>/dev/null || true
timedatectl set-timezone "$TZ_NAME"

step "Quiet boot (no rainbow, logo or text on screen)"
BOOT=/boot/firmware; [ -f "$BOOT/cmdline.txt" ] || BOOT=/boot
CFGTXT="$BOOT/config.txt"; CMD="$BOOT/cmdline.txt"
[ -f "$CMD.alx-backup" ] || cp "$CMD" "$CMD.alx-backup"
grep -q '^disable_splash=1' "$CFGTXT" || echo 'disable_splash=1' >> "$CFGTXT"
grep -q '^dtparam=watchdog=on' "$CFGTXT" || echo 'dtparam=watchdog=on' >> "$CFGTXT"
sed -i 's/console=tty1/console=tty3/' "$CMD"
for opt in quiet loglevel=3 logo.nologo vt.global_cursor_default=0 consoleblank=0; do
  grep -qw -- "$opt" "$CMD" || sed -i "1 s/\$/ $opt/" "$CMD"
done

step "Done"
echo "Installed $VER to $ROOT. Reboot to start:  sudo reboot"
echo "Afterwards:  alxctl status   (version and health)"
echo "             journalctl -u alx -f   (live log)"
