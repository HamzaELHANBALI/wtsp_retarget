#!/bin/bash

# ============================================================================
# Prevent Mac from Sleeping - Keep System Awake
# ============================================================================
# 
# This script prevents your Mac from going to sleep while the WhatsApp bot is running.
# It uses macOS's built-in 'caffeinate' command to keep the system awake.
#
# Usage:
#   bash prevent_sleep.sh          # Start preventing sleep (runs in background)
#   bash prevent_sleep.sh stop     # Stop preventing sleep
#   bash prevent_sleep.sh status   # Check if sleep prevention is active
#
# The script will keep your Mac awake until you stop it or close the terminal.
# ============================================================================

SCRIPT_NAME="prevent_sleep.sh"
PID_FILE="/tmp/whatsapp_bot_prevent_sleep.pid"
LOG_FILE="/tmp/whatsapp_bot_prevent_sleep.log"

# Function to start preventing sleep
start_prevent_sleep() {
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "⚠️  Sleep prevention is already running (PID: $OLD_PID)"
            echo "   To stop it, run: bash prevent_sleep.sh stop"
            return 1
        else
            # Stale PID file, remove it
            rm -f "$PID_FILE"
        fi
    fi
    
    echo "☕ Starting sleep prevention..."
    echo "   Your Mac will stay awake while this is running"
    echo "   Press Ctrl+C to stop, or run: bash prevent_sleep.sh stop"
    echo ""
    
    # Start caffeinate in background
    # -d: Prevent display from sleeping
    # -i: Prevent system from idle sleeping
    # -m: Prevent disk from sleeping
    # -s: Prevent system from sleeping (only on AC power)
    # -u: Simulate user activity
    nohup caffeinate -d -i -m -s -u > "$LOG_FILE" 2>&1 &
    CAFFEINATE_PID=$!
    
    # Save PID to file
    echo $CAFFEINATE_PID > "$PID_FILE"
    
    echo "✅ Sleep prevention started (PID: $CAFFEINATE_PID)"
    echo "   Your Mac will stay awake until you stop this script"
    echo ""
    echo "💡 To stop sleep prevention:"
    echo "   bash prevent_sleep.sh stop"
    echo ""
    echo "💡 To check status:"
    echo "   bash prevent_sleep.sh status"
    
    # Wait for the process (optional - can run in background)
    wait $CAFFEINATE_PID
}

# Function to stop preventing sleep
stop_prevent_sleep() {
    if [ ! -f "$PID_FILE" ]; then
        echo "ℹ️  Sleep prevention is not running (no PID file found)"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "ℹ️  Sleep prevention process not found (PID: $PID)"
        rm -f "$PID_FILE"
        return 1
    fi
    
    echo "🛑 Stopping sleep prevention (PID: $PID)..."
    kill "$PID" 2>/dev/null
    
    # Wait a bit and check if it's still running
    sleep 1
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  Process still running, forcing kill..."
        kill -9 "$PID" 2>/dev/null
    fi
    
    rm -f "$PID_FILE"
    echo "✅ Sleep prevention stopped"
    echo "   Your Mac can now sleep normally"
}

# Function to check status
check_status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "ℹ️  Sleep prevention is not running"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Sleep prevention is ACTIVE (PID: $PID)"
        echo "   Your Mac will stay awake"
        echo ""
        echo "💡 To stop: bash prevent_sleep.sh stop"
        return 0
    else
        echo "ℹ️  Sleep prevention is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Main script logic
case "${1:-start}" in
    start)
        start_prevent_sleep
        ;;
    stop)
        stop_prevent_sleep
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 [start|stop|status]"
        echo ""
        echo "Commands:"
        echo "  start  - Start preventing sleep (default)"
        echo "  stop   - Stop preventing sleep"
        echo "  status - Check if sleep prevention is active"
        exit 1
        ;;
esac

