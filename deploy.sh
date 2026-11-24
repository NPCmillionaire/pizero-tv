#!/usr/bin/env bash
# Install or update pizero-tv on a Pi:   ./deploy.sh [host]   (default: pizero)
#
# Copies the suite to <host>:~/pizero-tv, links `tv` into ~/.local/bin, installs the
# autostart entry, and restarts the display host. The old ~/tv install is left in place;
# its ~/.local/bin shortcuts are moved to ~/.local/bin/gemini-archive/ the first time.
set -euo pipefail
HOST=${1:-pizero}
cd "$(dirname "$0")"

rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude '.superpowers' --exclude '__pycache__' \
  --exclude 'tests' --exclude 'docs' --exclude '*.log' \
  ./ "$HOST:pizero-tv/"

# One short ssh call; the remote script runs detached so a dropped wifi link can't
# leave the install half done.
ssh -o ConnectTimeout=10 "$HOST" 'cat > /tmp/pizero-tv-install.sh <<"EOS"
set -u
mkdir -p ~/.local/bin ~/.config/autostart ~/.local/state/pizero-tv ~/.config/pizero-tv
if [ -L ~/.local/bin/tv ] && [ "$(readlink ~/.local/bin/tv)" != "$HOME/pizero-tv/bin/tv" ]; then
  mkdir -p ~/.local/bin/gemini-archive
  for l in ~/.local/bin/*; do
    [ -L "$l" ] && case "$(readlink "$l")" in *"/tv/"*|*"/tv") mv "$l" ~/.local/bin/gemini-archive/ ;; esac
  done
fi
ln -sfn ~/pizero-tv/bin/tv ~/.local/bin/tv
command -v mpv >/dev/null || echo "note: video channels need mpv (sudo apt install -y mpv)"
[ -x ~/.local/bin/yt-dlp ] || command -v yt-dlp >/dev/null || echo "note: video channels need yt-dlp in ~/.local/bin"
cp ~/pizero-tv/autostart/pizero-tv.desktop ~/.config/autostart/
[ -f ~/.config/pizero-tv/config.toml ] || cp ~/pizero-tv/config.example.toml ~/.config/pizero-tv/config.toml
[ -x ~/tv/tv ] && ~/tv/tv stop >/dev/null 2>&1
old=$(pgrep -f "^/usr/bin/python3 -m tvkit|^python3 -m tvkit")
if [ -n "$old" ]; then
  kill $old
  for i in $(seq 1 30); do kill -0 $old 2>/dev/null || break; sleep 0.5; done
  sleep 5                               # lwrespawn (if it started the host) brings it back
fi
pgrep -f "python3 -m tvkit" >/dev/null || ~/pizero-tv/bin/tv start
echo "install finished $(date)"
EOS
setsid nohup bash /tmp/pizero-tv-install.sh > /tmp/pizero-tv-install.log 2>&1 < /dev/null &'
echo "Deployed to $HOST. Install log on the Pi: /tmp/pizero-tv-install.log"
ssh -o ConnectTimeout=10 "$HOST" 'command -v mpv >/dev/null || echo "Video channels need mpv: sudo apt install -y mpv"; [ -x ~/.local/bin/yt-dlp ] || command -v yt-dlp >/dev/null || echo "Video channels need a current yt-dlp in ~/.local/bin (see README)"' || true
