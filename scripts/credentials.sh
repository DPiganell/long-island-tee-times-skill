#!/usr/bin/env bash
# One-time setup: store golf booking credentials in macOS Keychain.
# Run this once, then your tee-times skill will retrieve them automatically.
# Credentials are never written to disk — only stored in Keychain.

set -e

echo "=== Golf Booking Credential Setup ==="
echo ""

# --- Optional: Playwright headless browser ---
echo "--- Headless browser (optional — for Swan Lake & Spring Lake) ---"
echo "Enables live tee times from courses that don't have a public API."
read -rp "Install Playwright headless browser support? [y/N] " install_pw
if [[ "$install_pw" =~ ^[Yy]$ ]]; then
  echo "Installing Playwright Python package..."
  pip3 install --quiet playwright
  echo "Installing Chromium browser..."
  python3 -m playwright install chromium
  echo "Playwright ready. Use --headless flag: /tee-times Saturday morning 2 --headless"
else
  echo "Skipped. Add --headless to any search to install on first use."
fi
echo ""

# --- GolfNow ---
echo "--- GolfNow ---"
read -rp "GolfNow email: " golfnow_email
security delete-generic-password -s "tee-times-golfnow" 2>/dev/null || true
security add-generic-password \
  -s "tee-times-golfnow" \
  -a "$golfnow_email" \
  -w
echo "GolfNow credentials stored."
echo ""

# --- NYS Parks ---
echo "--- NYS Parks (Bethpage / Sunken Meadow) ---"
read -rp "NYS Parks email (leave blank to skip): " nysparks_email
if [[ -n "$nysparks_email" ]]; then
  security delete-generic-password -s "tee-times-nysparks" 2>/dev/null || true
  security add-generic-password \
    -s "tee-times-nysparks" \
    -a "$nysparks_email" \
    -w
  echo "NYS Parks credentials stored."
else
  echo "Skipped."
fi
echo ""

# --- Suffolk County WebTrac (Timber Point, West Sayville, Indian Island, Bergen Point) ---
echo "--- Suffolk County WebTrac (Timber Point, West Sayville, Indian Island, Bergen Point) ---"
echo "Login uses your Suffolk County Parks account (the same one tied to your Green Key)."
read -rp "Suffolk County WebTrac username (leave blank to skip): " webtrac_user
if [[ -n "$webtrac_user" ]]; then
  security delete-generic-password -s "tee-times-webtrac" 2>/dev/null || true
  security add-generic-password \
    -s "tee-times-webtrac" \
    -a "$webtrac_user" \
    -w
  echo "WebTrac credentials stored."
else
  echo "Skipped. Suffolk County courses will show as link-only entries."
fi
echo ""

# NOTE: Chronogolf no longer needs a session cookie — the marketplace/v2/teetimes
# API works anonymously when given the right course UUIDs. The credential prompt
# was dropped. If you still have an old `tee-times-chronogolf-session` entry, it's
# harmless but you can clean it up with:
#   security delete-generic-password -s tee-times-chronogolf-session

echo "Done. Run 'python3 ~/.claude/skills/tee-times/scripts/search.py --help' to test."
echo ""
echo "To verify stored credentials (shows email only, not password):"
echo "  security find-generic-password -s tee-times-golfnow"
echo ""
echo "To delete a stored credential:"
echo "  security delete-generic-password -s tee-times-golfnow"
