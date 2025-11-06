# WhatsApp Retargeting Solution for Saudi Arabia

A comprehensive WhatsApp bulk messaging solution optimized for retargeting Saudi Arabia customers. This solution combines the best features from three different approaches:

## Features

### ✅ Anti-Detection Automation
- Stealth browser automation with Selenium
- Human-like typing patterns
- Natural delays and behavior simulation
- Number verification before sending

### ✅ Number Rotation Strategy
- Distributes load across multiple WhatsApp numbers
- Prevents hitting daily limits per number
- Automatic daily limit reset
- Tracks usage per number

### ✅ Smart Delay Patterns
- Variable delays between messages (25-40 seconds)
- Automatic breaks every 5 messages (1-1.5 minutes)
- Longer breaks every 10 messages (2-3 minutes)
- Random pauses to mimic human behavior

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have Chrome browser installed (required for Selenium)

3. Install ChromeDriver:
```bash
# macOS
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
```

## Usage

### Basic Usage

```python
from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter

# Initialize with your Saudi WhatsApp numbers
retargeter = SaudiWhatsAppRetargeter(
    saudi_numbers=[
        '+966501234567',  # Your WhatsApp numbers
        '+966502345678',
        '+966503456789'
    ],
    daily_limit_per_number=40
)

# List of contacts to retarget
contacts = [
    '+966501111111',
    '+966502222222',
]

# Message template (supports Arabic)
message = """السلام عليكم ورحمة الله وبركاته

عزيزي العميل، نود أن نعلمك بعروضنا الحصرية الجديدة!

شكراً لثقتك بنا."""

# Send messages
try:
    retargeter.send_bulk_messages(
        contacts_list=contacts,
        message_template=message,
        prioritize_engaged=True
    )
finally:
    retargeter.close()
```

### Using CSV File

```python
import pandas as pd
from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter

# Load customer data
customers_df = pd.read_csv('saudi_customers.csv')
# CSV should have: phone, name (optional), last_contact (optional)

retargeter = SaudiWhatsAppRetargeter(
    saudi_numbers=['+966501234567', '+966502345678'],
    daily_limit_per_number=40
)

# Personalized message
message = """السلام عليكم {name}

نود أن نعلمك بعروضنا الحصرية الجديدة!"""

retargeter.send_bulk_messages(
    contacts_list=customers_df,
    message_template=message,
    prioritize_engaged=True
)
```

## Key Features Explained

### 1. Number Rotation
- Automatically rotates between multiple WhatsApp numbers
- Prevents any single number from hitting daily limits
- Tracks usage and resets daily

### 2. Human-like Behavior
- Natural typing patterns with variable speeds
- Random pauses (like thinking)
- Smart delays between messages
- Automatic breaks to avoid detection

### 3. Verification & Safety
- Verifies numbers are on WhatsApp before sending
- Verifies chat opened successfully
- Confirms message delivery
- Retry logic for failed messages

### 4. Prioritization
- Can prioritize engaged users if data available
- Sorts by last contact date
- Sorts by engagement level

## Configuration

### Daily Limits
- Default: 40 messages per number per day
- Adjustable per your needs
- Conservative limits help avoid blocking

### Delay Settings
- Base delay: 25-40 seconds between messages
- Break every 5 messages: 60-90 seconds
- Break every 10 messages: 120-180 seconds
- Random pauses: 5% chance of 45-75 seconds

## Important Notes

⚠️ **WhatsApp Terms of Service**: Make sure you comply with WhatsApp's terms of service. This tool is for legitimate business use only.

⚠️ **Rate Limits**: 
- Start with conservative limits (40 per number)
- Monitor for any blocking or warnings
- Adjust limits based on your account health

⚠️ **Phone Number Format**:
- Saudi numbers should be in format: +966XXXXXXXXX
- The tool automatically formats numbers if needed

## Troubleshooting

### QR Code Login
- First run will require scanning QR code
- Keep browser window open during sending
- Don't log out of WhatsApp Web

### ChromeDriver Issues
- Make sure ChromeDriver version matches Chrome version
- Update ChromeDriver if needed: `brew upgrade chromedriver`

### Message Failures
- Check if number is on WhatsApp
- Verify internet connection
- Check if WhatsApp Web is still logged in

## Statistics

After each campaign, you'll see:
- Total processed
- Successfully sent
- Failed messages
- Success rate
- Usage per number

## Example Output

```
============================================================
Starting bulk WhatsApp retargeting for Saudi Arabia
============================================================

Total contacts to process: 100
Using 3 WhatsApp numbers
Daily limit per number: 40

[1/100] Processing: +966501111111
Using number: +966501234567 (Usage: 0/40)
✓ Message sent successfully to +966501111111

Taking a short break (75 seconds) after 5 messages...

============================================================
Campaign Complete!
============================================================
Total processed: 100
Successfully sent: 95
Failed: 5
Success rate: 95.00%

Number usage summary:
  +966501234567: 33/40 messages
  +966502345678: 32/40 messages
  +966503456789: 30/40 messages
============================================================
```

## Support

For issues or questions, check the code comments or modify the configuration as needed.

