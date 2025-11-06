# How the WhatsApp Retargeting Script Works

## Overview

This script uses **WhatsApp Web** to send bulk messages to your Saudi Arabia customers. It works with **ANY WhatsApp number** (Moroccan, Saudi, or any other country) - the sender's country doesn't matter.

## How It Works

### 1. **WhatsApp Web Automation**
- The script opens Chrome browser automatically
- Navigates to `web.whatsapp.com`
- You scan the QR code with your **Moroccan WhatsApp** (or any WhatsApp number)
- Once logged in, the script can send messages through WhatsApp Web

### 2. **What You Need**

#### ✅ Required:
1. **One WhatsApp number** (your Moroccan number works perfectly)
   - Can be from any country (Morocco, Saudi, etc.)
   - Must be able to scan QR code on WhatsApp Web

2. **CSV file with Saudi customers**
   - Must have a column with phone numbers (named `phone` or `number`)
   - Optional: `name` column for personalization
   - Optional: `last_contact` column for prioritizing engaged users

3. **Python packages** (install with `pip install -r requirements.txt`)
   - selenium
   - pandas

4. **Chrome browser** + ChromeDriver installed

### 3. **How It Sends Messages**

The script:
1. Opens WhatsApp Web in Chrome
2. You log in with your Moroccan WhatsApp (scan QR code)
3. Reads your CSV file with Saudi customer numbers
4. For each customer:
   - Formats the phone number (ensures +966 format for Saudi)
   - Verifies the number is on WhatsApp
   - Opens the chat
   - Types the message with human-like delays
   - Sends the message
   - Waits with smart delays (25-40 seconds between messages)
   - Takes breaks every 5-10 messages

### 4. **Important Points**

#### ✅ Your Moroccan WhatsApp Number:
- **Works perfectly** - WhatsApp Web doesn't care about the sender's country
- You can send to Saudi customers from any WhatsApp number
- The script handles phone number formatting automatically

#### ✅ Saudi Customer Numbers:
- Script automatically formats to +966XXXXXXXXX format
- Verifies each number is on WhatsApp before sending
- Handles different input formats (with/without country code, with/without +)

#### ✅ Anti-Detection Features:
- Human-like typing patterns
- Variable delays between messages
- Automatic breaks to avoid detection
- Stealth browser settings

## Step-by-Step Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install ChromeDriver
```bash
# macOS
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
```

### Step 3: Prepare Your CSV File

Create a CSV file (e.g., `saudi_customers.csv`) with your Saudi customers:

```csv
phone,name
+966501111111,Ahmed Al-Saud
+966502222222,Fatima Al-Rashid
+966503333333,Mohammed Al-Otaibi
```

Or simpler format:
```csv
phone
+966501111111
+966502222222
+966503333333
```

### Step 4: Create Your Script

```python
from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter
import pandas as pd

# Initialize (works with ANY WhatsApp number - Moroccan, Saudi, etc.)
retargeter = SaudiWhatsAppRetargeter(
    daily_limit=40  # Max messages per day
)

# Load your CSV with Saudi customers
contacts_df = pd.read_csv('saudi_customers.csv')

# Your message (supports Arabic and English)
message = """السلام عليكم ورحمة الله وبركاته

عزيزي {name}، نود أن نعلمك بعروضنا الحصرية الجديدة!

شكراً لثقتك بنا."""

# Send messages
try:
    retargeter.send_bulk_messages(
        contacts_list=contacts_df,
        message_template=message,
        prioritize_engaged=True
    )
finally:
    retargeter.close()
```

### Step 5: Run the Script

```bash
python your_script.py
```

**What happens:**
1. Chrome browser opens automatically
2. WhatsApp Web page loads
3. **You scan the QR code with your Moroccan WhatsApp**
4. Press Enter after logging in
5. Script starts sending messages automatically

## Example Workflow

```
1. You run: python send_messages.py
   ↓
2. Chrome opens → WhatsApp Web loads
   ↓
3. QR code appears on screen
   ↓
4. You open WhatsApp on your Moroccan phone
   ↓
5. You scan the QR code
   ↓
6. You press Enter in terminal
   ↓
7. Script reads CSV file
   ↓
8. For each Saudi customer:
   - Formats number: +966XXXXXXXXX
   - Verifies on WhatsApp
   - Opens chat
   - Types message (human-like)
   - Sends message
   - Waits 25-40 seconds
   - Takes breaks every 5-10 messages
   ↓
9. Shows statistics at the end
```

## Phone Number Formatting

The script automatically handles different formats:

**Input formats (all work):**
- `966501111111` → Converts to `+966501111111`
- `0501111111` → Converts to `+966501111111`
- `+966501111111` → Keeps as is
- `00966501111111` → Converts to `+966501111111`

**Output:** Always `+966XXXXXXXXX` format

## Daily Limits

- **Default:** 40 messages per day
- **Why:** To avoid WhatsApp rate limiting and blocking
- **Adjustable:** Change `daily_limit` parameter
- **Resets:** Automatically resets at midnight

## Smart Delays

The script uses intelligent delays to mimic human behavior:

- **Base delay:** 25-40 seconds between messages
- **Short break:** 60-90 seconds every 5 messages
- **Long break:** 2-3 minutes every 10 messages
- **Random pauses:** 5% chance of extra 45-75 second pause

## Troubleshooting

### QR Code Not Scanning?
- Make sure your Moroccan WhatsApp is active
- Check internet connection
- Try refreshing the page

### Messages Not Sending?
- Check if customer numbers are on WhatsApp
- Verify you're still logged into WhatsApp Web
- Check internet connection

### ChromeDriver Issues?
- Make sure ChromeDriver version matches Chrome version
- Update ChromeDriver: `brew upgrade chromedriver`

## Summary

**What you need:**
- ✅ One WhatsApp number (Moroccan works perfectly)
- ✅ CSV file with Saudi customer phone numbers
- ✅ Python + Chrome + ChromeDriver installed

**What the script does:**
- ✅ Opens WhatsApp Web automatically
- ✅ You log in with your Moroccan WhatsApp
- ✅ Sends messages to Saudi customers automatically
- ✅ Handles phone number formatting
- ✅ Uses human-like behavior to avoid detection
- ✅ Tracks statistics and daily limits

**The key point:** Your Moroccan WhatsApp number works perfectly! WhatsApp Web doesn't care about the sender's country - you can send to Saudi customers from any WhatsApp number.

