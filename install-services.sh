#!/usr/bin/env bash
#
# Sets up the Raspberry Pi Adhan clock to run and auto-start on boot:
#   - installs dependencies (Flask, mpv)
#   - adhan-admin.service    -> the management web panel on :8080
#   - adhan-display.service  -> the wall-display web server on :8000
#   - reinstalls the adhan cron jobs (if a settings.ini already exists)
#   - optional kiosk browser autostart:   ./install-services.sh --with-kiosk
#
# Paths and the run-user are auto-detected, so this works regardless of the
# folder name (adhan-disp, adhan-display, ...) or username.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="$(whoami)"
RUN_HOME="$HOME"
PY="$(command -v python3)"

echo "==> Repo:  $REPO_DIR"
echo "==> User:  $RUN_USER"
echo "==> Python: $PY"
echo

# --- 1. Dependencies -------------------------------------------------------
echo "==> Installing dependencies (python3-flask, mpv)..."
sudo apt-get update -qq
sudo apt-get install -y python3-flask mpv

# --- 2. Admin panel service (port 8080) ------------------------------------
echo "==> Installing adhan-admin.service (web panel, :8080)..."
sudo tee /etc/systemd/system/adhan-admin.service >/dev/null <<EOF
[Unit]
Description=Adhan Admin Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR/webadmin
ExecStart=$PY app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- 3. Display server (port 8000) -----------------------------------------
echo "==> Installing adhan-display.service (wall display, :8000)..."
sudo tee /etc/systemd/system/adhan-display.service >/dev/null <<EOF
[Unit]
Description=Adhan Display HTTP Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR/adhan-display
ExecStart=$PY -m http.server 8000 --bind 0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now adhan-admin.service
sudo systemctl enable --now adhan-display.service

# --- 4. Adhan cron jobs -----------------------------------------------------
# Playback is driven by cron (which is persistent across reboots on its own).
# If a settings.ini already exists we refresh the jobs so they use the current
# play_adhan.py commands; otherwise we remind you to run the setup once.
if [ -f "$REPO_DIR/settings.ini" ]; then
  echo "==> Reinstalling adhan cron jobs from settings.ini..."
  ( cd "$REPO_DIR" && "$PY" updateAzaanTimers.py ) || \
    echo "!!  Could not reinstall cron automatically; run updateAzaanTimers.py by hand."
else
  echo "!!  No settings.ini yet. Set your location + install cron with, e.g.:"
  echo "      cd $REPO_DIR && python3 updateAzaanTimers.py --lat <LAT> --lon <LON> --method ISNA"
fi

# --- 5. Optional kiosk browser autostart -----------------------------------
if [ "${1:-}" = "--with-kiosk" ]; then
  CHROMIUM="$(command -v chromium-browser || command -v chromium || true)"
  if [ -z "$CHROMIUM" ]; then
    echo "!!  --with-kiosk requested but no chromium binary found; skipping kiosk."
  else
    echo "==> Setting up kiosk autostart with $CHROMIUM ..."
    AUTOSTART_DIR="$RUN_HOME/.config/lxsession/LXDE-pi"
    mkdir -p "$AUTOSTART_DIR"
    tee "$AUTOSTART_DIR/autostart" >/dev/null <<EOF
@xset s off
@xset -dpms
@xset s noblank
@bash -c "sleep 10"
@$CHROMIUM --noerrdialogs --disable-infobars --kiosk http://localhost:8000
EOF
    echo "    Kiosk autostart written to $AUTOSTART_DIR/autostart"
    echo "    (Applies on next desktop login/reboot.)"
  fi
fi

echo
echo "==> Done. Status:"
systemctl --no-pager status adhan-admin.service   | sed -n '1,3p' || true
systemctl --no-pager status adhan-display.service | sed -n '1,3p' || true
echo
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "    Admin panel:  http://${IP:-<pi-ip>}:8080"
echo "    Wall display: http://${IP:-<pi-ip>}:8000"
