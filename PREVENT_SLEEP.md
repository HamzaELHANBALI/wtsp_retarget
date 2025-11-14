# Prevent Mac from Sleeping

This script keeps your Mac awake while the WhatsApp bot is running.

## Quick Start

### Start preventing sleep:
```bash
bash prevent_sleep.sh
```

### Stop preventing sleep:
```bash
bash prevent_sleep.sh stop
```

### Check if it's running:
```bash
bash prevent_sleep.sh status
```

## How It Works

The script uses macOS's built-in `caffeinate` command to:
- ✅ Prevent display from sleeping
- ✅ Prevent system from idle sleeping  
- ✅ Prevent disk from sleeping
- ✅ Keep system awake (on AC power)
- ✅ Simulate user activity

## Usage Examples

### Run in background:
```bash
bash prevent_sleep.sh &
```

### Run and keep terminal open:
```bash
bash prevent_sleep.sh
# Press Ctrl+C to stop
```

### Stop from another terminal:
```bash
bash prevent_sleep.sh stop
```

## Integration with WhatsApp Bot

You can run this script before starting the WhatsApp bot:

```bash
# Terminal 1: Keep Mac awake
bash prevent_sleep.sh

# Terminal 2: Run WhatsApp bot
streamlit run streamlit_app.py
```

Or run both in the same terminal:

```bash
# Start sleep prevention in background
bash prevent_sleep.sh &

# Run WhatsApp bot
streamlit run streamlit_app.py

# When done, stop sleep prevention
bash prevent_sleep.sh stop
```

## Troubleshooting

### Script won't start?
- Make sure you have execute permissions: `chmod +x prevent_sleep.sh`
- Or run with: `bash prevent_sleep.sh`

### Can't stop the script?
- Check if it's running: `bash prevent_sleep.sh status`
- Force stop: `kill $(cat /tmp/whatsapp_bot_prevent_sleep.pid)`
- Or kill all caffeinate processes: `pkill caffeinate`

### Mac still goes to sleep?
- Check if script is running: `bash prevent_sleep.sh status`
- Make sure you're on AC power (not battery) for full sleep prevention
- Check System Settings → Energy Saver → Prevent automatic sleeping

## Notes

- The script will keep your Mac awake until you stop it
- It's safe to run - it only prevents sleep, doesn't change system settings
- When you stop the script, your Mac will return to normal sleep behavior
- The script saves its process ID in `/tmp/whatsapp_bot_prevent_sleep.pid`

