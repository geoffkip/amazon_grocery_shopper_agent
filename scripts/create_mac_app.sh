#!/bin/bash
# Create macOS .app bundle for Amazon Fresh Fetch

APP_NAME="Amazon Fresh Fetch"
APP_DIR="${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

# Create app bundle structure
mkdir -p "${MACOS_DIR}"
mkdir -p "${RESOURCES_DIR}"

# Create the launcher script
cat > "${MACOS_DIR}/launcher" << 'EOF'
#!/bin/bash

# Get the directory where the app is located
APP_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

# Open Terminal and run the launch script
osascript << APPLESCRIPT
tell application "Terminal"
    activate
    do script "cd '$APP_DIR' && ./scripts/launch.sh"
end tell
APPLESCRIPT
EOF

# Make launcher executable
chmod +x "${MACOS_DIR}/launcher"

# Create Info.plist
cat > "${CONTENTS_DIR}/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.amazon.freshfetch</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
</dict>
</plist>
EOF

echo "✅ Created ${APP_NAME}.app"
echo ""
echo "You can now:"
echo "1. Double-click '${APP_NAME}.app' to launch"
echo "2. Drag it to your Applications folder"
echo "3. Add it to your Dock"
EOF

chmod +x create_mac_app.sh
