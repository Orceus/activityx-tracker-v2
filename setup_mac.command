#!/bin/bash
# ActivityX macOS Setup
# Installs the tracker as a LaunchAgent so it runs silently on every login.

set -e

INSTALL_DIR="$HOME/Library/Application Support/ActivityX"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.activityx.tracker.plist"
CONTROLLER_PLIST="$PLIST_DIR/com.activityx.controller.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  ActivityX Setup"
echo "========================================"
echo ""

# ── Install files ──────────────────────────────────────────────────────────────
echo "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"

cp "$SCRIPT_DIR/activity_tracker"            "$INSTALL_DIR/activity_tracker"
cp "$SCRIPT_DIR/activity_tracker_controller" "$INSTALL_DIR/activity_tracker_controller"
cp "$SCRIPT_DIR/config.py"                   "$INSTALL_DIR/config.py"
if [ -f "$SCRIPT_DIR/version.txt" ]; then
    cp "$SCRIPT_DIR/version.txt" "$INSTALL_DIR/version.txt"
fi
chmod +x "$INSTALL_DIR/activity_tracker"
chmod +x "$INSTALL_DIR/activity_tracker_controller"

# ── Create LaunchAgent plist ───────────────────────────────────────────────────
mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.activityx.tracker</string>

    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/activity_tracker</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/tracker.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/tracker.log</string>
</dict>
</plist>
EOF

# ── Create controller LaunchAgent plist ──────────────────────────────────────
cat > "$CONTROLLER_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.activityx.controller</string>

    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/activity_tracker_controller</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/controller.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/controller.log</string>
</dict>
</plist>
EOF

# ── Load it now (no reboot needed) ────────────────────────────────────────────
# Unload first in case it was previously loaded
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl unload "$CONTROLLER_PLIST" 2>/dev/null || true
launchctl load -w "$PLIST_FILE"
launchctl load -w "$CONTROLLER_PLIST"

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "The tracker is now running in the background."
echo "It will start automatically on every login."
echo ""
echo "To check status:  launchctl list | grep activityx"
echo "To stop:          launchctl unload $PLIST_FILE && launchctl unload $CONTROLLER_PLIST"
echo "To view logs:     tail -f $INSTALL_DIR/tracker.log"
