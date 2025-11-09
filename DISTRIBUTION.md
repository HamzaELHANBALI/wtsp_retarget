# Distribution Guide: Running on Another Mac

This guide explains how to run the WhatsApp Bot on a Mac that doesn't have Python installed.

## Option 1: Standalone Executable (Recommended)

### Building the Standalone App

1. **On your Mac (with Python installed):**

   ```bash
   # Make the build script executable
   chmod +x build_standalone.sh
   
   # Run the build script
   ./build_standalone.sh
   ```

2. **The standalone executable will be created in:**
   - `dist/WhatsAppBot` (single file executable)

3. **To distribute:**
   - Copy the `dist/WhatsAppBot` file to the other Mac
   - Make it executable: `chmod +x WhatsAppBot`
   - Run it: `./WhatsAppBot`

## Option 2: macOS .app Bundle (Easier for End Users)

### Building the .app Bundle

1. **On your Mac (with Python installed):**

   ```bash
   # Make the build script executable
   chmod +x build_app_bundle.sh
   
   # Run the build script
   ./build_app_bundle.sh
   ```

2. **The .app bundle will be created in:**
   - `dist/WhatsAppBot.app` (macOS application bundle)

3. **To distribute:**
   - Copy the `dist/WhatsAppBot.app` folder to the other Mac
   - Double-click it to run
   - **Note:** On first run, macOS may block it. Right-click and select "Open", then allow it in System Settings

## Option 3: Simple Setup Script (Alternative)

If building standalone apps doesn't work, you can create a setup script that installs everything automatically.

### Creating a Setup Script

1. **Create `setup_and_run.sh`:**

   ```bash
   #!/bin/bash
   echo "🚀 WhatsApp Bot Setup"
   echo "===================="
   
   # Check if Homebrew is installed
   if ! command -v brew &> /dev/null; then
       echo "📦 Installing Homebrew..."
       /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   fi
   
   # Install Python
   if ! command -v python3 &> /dev/null; then
       echo "📦 Installing Python..."
       brew install python3
   fi
   
   # Install dependencies
   echo "📦 Installing dependencies..."
   pip3 install -r requirements.txt
   
   # Run the app
   echo "✅ Setup complete! Starting app..."
   streamlit run streamlit_app.py
   ```

2. **Make it executable:**
   ```bash
   chmod +x setup_and_run.sh
   ```

3. **To distribute:**
   - Copy the entire project folder to the other Mac
   - Double-click `setup_and_run.sh` or run: `./setup_and_run.sh`
   - The script will automatically install everything needed

## Option 4: Using Docker (Advanced)

If the other Mac has Docker installed, you can containerize the app.

### Creating a Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0"]
```

### Building and Running

```bash
# Build the Docker image
docker build -t whatsapp-bot .

# Run the container
docker run -p 8501:8501 whatsapp-bot
```

## Troubleshooting

### macOS Security Warnings

If macOS blocks the app:

1. **For .app bundles:**
   - Right-click the app
   - Select "Open"
   - Click "Open" in the security dialog
   - Go to System Settings > Privacy & Security
   - Allow the app

2. **For standalone executables:**
   - Open Terminal
   - Run: `xattr -cr WhatsAppBot`
   - Then run: `./WhatsAppBot`

### Missing Dependencies

If the standalone app doesn't work:

1. Try Option 3 (Setup Script) instead
2. Or manually install Python and dependencies on the target Mac

### Chrome/Chromium Issues

The bot requires Chrome/Chromium for Selenium. Make sure Chrome is installed on the target Mac:

```bash
# Install Chrome via Homebrew
brew install --cask google-chrome
```

## Recommended Approach

**For non-technical users:** Use Option 2 (.app bundle) - it's the most user-friendly.

**For technical users:** Use Option 1 (standalone executable) - it's smaller and faster.

**If building fails:** Use Option 3 (setup script) - it's the most reliable.

