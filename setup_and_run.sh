#!/bin/bash

# Simple setup and run script for macOS
# This script automatically installs everything needed and runs the app
# 
# Usage:
#   1. Save this file as setup_and_run.sh
#   2. Make it executable: chmod +x setup_and_run.sh
#   3. Run it: ./setup_and_run.sh
#   4. The script will automatically clone the repository and set everything up

echo "🚀 WhatsApp Bot Setup"
echo "===================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "📦 Homebrew not found. Installing Homebrew..."
    echo "   (This may take a few minutes)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew is already installed"
fi

# Install Git if not installed
if ! command -v git &> /dev/null; then
    echo "📦 Git not found. Installing Git..."
    brew install git
else
    echo "✅ Git is already installed: $(git --version)"
fi

# Clone the repository if not already present
REPO_DIR="wtsp_retarget"
REPO_URL="https://github.com/HamzaELHANBALI/wtsp_retarget.git"

# Check if we're already in the repo directory (if script is inside the repo)
if [ -f "streamlit_app.py" ] && [ -f "whatsapp_bot.py" ]; then
    echo "✅ Already in the project directory"
    CURRENT_DIR=$(pwd)
else
    # We need to clone the repository
    if [ ! -d "$REPO_DIR" ]; then
        echo "📦 Repository not found. Cloning from GitHub..."
        echo "   Repository: $REPO_URL"
        git clone "$REPO_URL" "$REPO_DIR"
        
        if [ $? -ne 0 ]; then
            echo "❌ Error: Failed to clone repository"
            echo "   Please check:"
            echo "   1. The repository is public or you have access"
            echo "   2. Git is properly installed"
            echo "   3. Internet connection is working"
            exit 1
        fi
        
        cd "$REPO_DIR" || exit 1
        echo "✅ Repository cloned successfully"
    else
        echo "✅ Repository already exists"
        cd "$REPO_DIR" || exit 1
        echo "📦 Updating repository..."
        git pull
    fi
fi

# Install Python if not installed
if ! command -v python3 &> /dev/null; then
    echo "📦 Python not found. Installing Python..."
    brew install python3
else
    echo "✅ Python is already installed: $(python3 --version)"
fi

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ Virtual environment created and activated"
else
    echo "✅ Virtual environment already active"
fi

# Install dependencies
echo "📦 Installing dependencies..."
echo "   (This may take a few minutes)"
pip install --upgrade pip
pip install -r requirements.txt

# Setup OpenAI API key
echo ""
echo "🔑 Setting up OpenAI API key..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📋 Creating .env file from .env.example..."
        cp .env.example .env
    else
        echo "📋 Creating .env file..."
        touch .env
    fi
fi

# Check if a valid API key is already set
EXISTING_KEY=$(grep "^OPENAI_API_KEY=" .env 2>/dev/null | cut -d'=' -f2- | tr -d ' ' | head -1)

if [ -n "$EXISTING_KEY" ] && [[ "$EXISTING_KEY" == sk-* ]] && [ "$EXISTING_KEY" != "your-api-key-here" ]; then
    echo "✅ API key already configured in .env file"
else
    # No valid API key found, prompt for it
    echo ""
    echo "Please enter your OpenAI API key:"
    echo "   (You can get it from: https://platform.openai.com/api-keys)"
    echo "   (The key will be saved to .env file)"
    read -r USER_API_KEY
    
    if [ -z "$USER_API_KEY" ]; then
        echo "⚠️  Warning: No API key provided. You'll need to add it manually to .env file"
        echo "   Format: OPENAI_API_KEY=sk-..."
    else
        # Add or update OPENAI_API_KEY in .env
        if grep -q "^OPENAI_API_KEY=" .env 2>/dev/null; then
            # Update existing key
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$USER_API_KEY|" .env
            else
                # Linux
                sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$USER_API_KEY|" .env
            fi
        else
            # Add new key
            echo "OPENAI_API_KEY=$USER_API_KEY" >> .env
        fi
        echo "✅ API key saved to .env file"
    fi
fi

# Check if Chrome is installed
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null; then
    echo "⚠️  Chrome/Chromium not found. Installing Chrome..."
    brew install --cask google-chrome
else
    echo "✅ Chrome is already installed"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting WhatsApp Bot..."
echo "   The app will open in your browser at http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

# Run the app
streamlit run streamlit_app.py

