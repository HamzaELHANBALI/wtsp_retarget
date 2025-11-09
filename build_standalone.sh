#!/bin/bash

# Build script to create a standalone macOS app
# This creates a standalone executable that doesn't require Python

echo "🔨 Building standalone macOS app..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

# Create the standalone executable
echo "📦 Creating standalone executable..."
pyinstaller --name="WhatsAppBot" \
    --onefile \
    --windowed \
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
    streamlit_app.py

echo "✅ Build complete!"
echo "📦 The standalone app is in: dist/WhatsAppBot"
echo ""
echo "To run on another Mac:"
echo "1. Copy the 'dist/WhatsAppBot' file to the other Mac"
echo "2. Make it executable: chmod +x WhatsAppBot"
echo "3. Run it: ./WhatsAppBot"

