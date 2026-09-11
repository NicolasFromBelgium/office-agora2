#!/usr/bin/env bash
# Install Office Agora under Apache at /office (dogscout.be/office).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WWW_LINK="/var/www/dogscout/office-agora"
VHOST="/etc/apache2/sites-available/dogscout.conf"
SERVICE_SRC="$ROOT/deploy/systemd/office-agora.service"
SERVICE_DST="/etc/systemd/system/office-agora.service"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Run ./scripts/bootstrap.sh first."
  exit 1
fi

echo "Linking $WWW_LINK → $ROOT"
ln -sfn "$ROOT" "$WWW_LINK"

SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  SUDO="sudo"
fi

echo "Enabling Apache proxy modules…"
$SUDO a2enmod proxy proxy_http headers rewrite

TMP="$(mktemp)"
python3 - "$VHOST" "$TMP" <<'PY'
import sys
from pathlib import Path

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
if "dogscout.be" not in text:
    if "ServerAlias" in text:
        text = text.replace("ServerAlias localhost", "ServerAlias dogscout.be www.dogscout.be localhost", 1)
    else:
        text = text.replace(
            "ServerName dogscout.local",
            "ServerName dogscout.local\n    ServerAlias dogscout.be www.dogscout.be localhost",
            1,
        )
if "ProxyPass /office" not in text:
    snippet = """
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Prefix "/office"
    ProxyPass /office http://127.0.0.1:8088
    ProxyPassReverse /office http://127.0.0.1:8088
"""
    text = text.replace("</VirtualHost>", snippet + "\n</VirtualHost>", 1)
dest.write_text(text, encoding="utf-8")
print("Prepared", dest)
PY
$SUDO cp "$TMP" "$VHOST"
rm -f "$TMP"

echo "Installing systemd service…"
$SUDO cp "$SERVICE_SRC" "$SERVICE_DST"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now office-agora.service
$SUDO apache2ctl configtest
$SUDO systemctl reload apache2

echo
echo "Office Agora should be at:"
echo "  http://dogscout.be/office"
echo "  http://127.0.0.1/office"
echo
$SUDO systemctl --no-pager --full status office-agora.service | head -20
