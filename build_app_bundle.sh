#!/bin/bash

# Build script to create a macOS .app bundle
# This creates a proper macOS application that can be double-clicked

echo "🔨 Building macOS .app bundle..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

# Create the .app bundle
echo "📦 Creating .app bundle..."
pyinstaller --name="WhatsAppBot" \
    --windowed \
    --onedir \
    --add-data="streamlit_app.py:." \
    --add-data="whatsapp_bot.py:." \
    --add-data="clean_order_csv.py:." \
    --hidden-import=streamlit \
    --hidden-import=selenium \
    --hidden-import=openai \
    --hidden-import=pandas \
    --hidden-import=dotenv \
    --hidden-import=pyperclip \
    --collect-all streamlit \
    --collect-all selenium \
    --icon=NONE \
    streamlit_app.py

# Create a proper .app bundle structure
echo "📦 Creating .app bundle structure..."
APP_NAME="WhatsAppBot.app"
APP_DIR="dist/$APP_NAME"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Create directory structure
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Move the executable
if [ -d "dist/WhatsAppBot" ]; then
    cp -r dist/WhatsAppBot/* "$MACOS_DIR/"
fi

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>WhatsAppBot</string>
    <key>CFBundleIdentifier</key>
    <string>com.whatsappbot.app</string>
    <key>CFBundleName</key>
    <string>WhatsApp Bot</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
</dict>
</plist>
EOF

echo "✅ Build complete!"
echo "📦 The .app bundle is in: dist/$APP_NAME"
echo ""
echo "To use on another Mac:"
echo "1. Copy the 'dist/$APP_NAME' folder to the other Mac"
echo "2. Double-click it to run (you may need to right-click and select 'Open' the first time)"
echo "3. If macOS blocks it, go to System Settings > Privacy & Security and allow it"

