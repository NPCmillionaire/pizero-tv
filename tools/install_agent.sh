#!/usr/bin/env bash
# Install the pizero-tv stats agent so the SYSTEM channel can show this machine.
#   ./tools/install_agent.sh           this Mac (a launchd agent) or this Linux box (a systemd user service)
#   ./tools/install_agent.sh arch      a Linux machine over ssh
# It serves read-only stats on port 8765 to private network addresses only. Remove with --uninstall.
set -euo pipefail
cd "$(dirname "$0")/.."
TARGET=${1:-}
DEST='$HOME/.local/share/pizero-tv-agent'

linux_install='set -e
mkdir -p ~/.local/share/pizero-tv-agent ~/.config/systemd/user
mv /tmp/pizero-tv-agent.py ~/.local/share/pizero-tv-agent/agent.py
cat > ~/.config/systemd/user/pizero-tv-agent.service <<UNIT
[Unit]
Description=pizero-tv stats agent (read-only, private networks only)
StartLimitIntervalSec=0
[Service]
ExecStart=/usr/bin/env python3 %h/.local/share/pizero-tv-agent/agent.py
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now pizero-tv-agent.service
systemctl --user restart pizero-tv-agent.service
loginctl show-user "$USER" -p Linger | grep -q yes || loginctl enable-linger "$USER" 2>/dev/null || \
  echo "note: run \"sudo loginctl enable-linger $USER\" so the agent keeps running when you are logged out"
sleep 2; curl -s localhost:8765/stats >/dev/null && echo "agent running on $(hostname):8765"'

if [ -n "$TARGET" ]; then
  scp -q tvkit/agent.py "$TARGET:/tmp/pizero-tv-agent.py"
  ssh "$TARGET" "$linux_install"
elif [ "$(uname)" = Darwin ]; then
  mkdir -p ~/.local/share/pizero-tv-agent ~/Library/LaunchAgents
  cp tvkit/agent.py ~/.local/share/pizero-tv-agent/agent.py
  PL=~/Library/LaunchAgents/research.legitbiz.pizero-tv-agent.plist
  cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>research.legitbiz.pizero-tv-agent</string>
  <key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$HOME/.local/share/pizero-tv-agent/agent.py</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
PLIST
  launchctl bootout "gui/$(id -u)" "$PL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PL"
  sleep 2; curl -s localhost:8765/stats >/dev/null && echo "agent running on $(hostname):8765"
else
  cp tvkit/agent.py /tmp/pizero-tv-agent.py
  bash -c "$linux_install"
fi
