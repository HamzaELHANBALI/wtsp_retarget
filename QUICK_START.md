# Quick Start Guide

## How to Run the Setup Script

If you get a **"Permission Denied"** error, use one of these methods:

### ✅ Method 1: Run with `bash` (Easiest - No permissions needed)
```bash
bash setup_and_run.sh
```

### ✅ Method 2: Make it executable first
```bash
chmod +x setup_and_run.sh
./setup_and_run.sh
```

### ✅ Method 3: Run with `sh`
```bash
sh setup_and_run.sh
```

## Why does this happen?

When you download or clone a file, it might not have execute permissions. Running it with `bash` or `sh` doesn't require execute permissions - it just tells the system to use the bash/shell interpreter to run the script.

## Full Instructions

1. **Download or clone the repository:**
   ```bash
   git clone https://github.com/HamzaELHANBALI/wtsp_retarget.git
   cd wtsp_retarget
   ```

2. **Run the setup script:**
   ```bash
   bash setup_and_run.sh
   ```

3. **Follow the prompts:**
   - The script will install everything automatically
   - Enter your OpenAI API key when prompted
   - Wait for installation to complete
   - The app will open in your browser

## Troubleshooting

### "Permission Denied" Error
- **Solution:** Use `bash setup_and_run.sh` instead of `./setup_and_run.sh`

### "Command not found: bash"
- **Solution:** Use `sh setup_and_run.sh` instead

### Script won't run at all
- Make sure you're in the correct directory
- Check that the file exists: `ls -la setup_and_run.sh`
- Try: `bash -x setup_and_run.sh` to see what's happening

## Need Help?

If you're still having issues:
1. Make sure you're on macOS (the script is designed for Mac)
2. Check that you have internet connection
3. Try running with verbose output: `bash -x setup_and_run.sh`
4. Contact support with the error message

