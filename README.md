# WhatsApp Bulk Messaging Bot with AI Auto-Responses

A modern, reliable WhatsApp automation tool for bulk messaging and AI-powered customer service.

## ✨ Features

- **📤 Bulk Messaging**: Send text and media (images/videos) to multiple contacts
- **🤖 AI Auto-Responses**: Automatically respond to customer messages using OpenAI
- **💬 Conversation Tracking**: Maintains context per customer for natural conversations
- **🔐 Persistent Sessions**: Scan QR code once, session saved for future runs
- **🌍 Multi-Language**: Supports Arabic and English (and other languages)
- **📊 Statistics**: Track messages sent, AI responses, and conversations
- **🎨 Streamlit UI**: Beautiful web interface for easy CSV uploads and management

## 🌟 NEW: Streamlit Web UI

We now have a beautiful, user-friendly web interface! Perfect for non-technical users.

### Quick Launch (Local)

```bash
# 1. Install dependencies (if not already done)
pip install -r requirements.txt

# 2. Set up API key in .env file (IMPORTANT!)
cp .env.example .env
nano .env  # Add your OpenAI API key

# 3. Launch the web UI
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

**🔐 Security Note:** The app loads API keys from the `.env` file automatically. Never expose your API key in the UI when deploying! See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions.

### UI Features

- **🧪 Test Message**: Send a test message to one number before bulk sending (NEW!)
- **📤 CSV Upload**: Drag and drop your contacts CSV file
- **✏️ Message Composer**: Write messages with variables (`{name}`, `{phone}`, `{custom_message}`)
- **📎 Media Attachments**: Upload images and videos directly through the UI
- **📊 Real-time Progress**: See messages being sent with live progress bars
- **🤖 AI Monitoring Dashboard**: Track and view AI auto-responses in real-time
- **⚙️ Easy Configuration**: Set API keys, delays, and system prompts without code
- **📈 Analytics**: View statistics and success rates
- **📥 Template Download**: Get a sample CSV template with one click

### CSV Format for UI

Your CSV should have these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `phone` | ✅ Yes | Phone number (with or without country code) |
| `name` | ❌ Optional | Contact name (defaults to "Customer") |
| `custom_message` | ❌ Optional | Custom message per contact |

**Example CSV:**
```csv
phone,name,custom_message
+966501234567,Ahmed,Special 20% discount just for you!
0502345678,Fatima,Thank you for being a loyal customer
966503456789,Mohammed,
```

Download the `contacts_template.csv` file or use the download button in the UI.

### 🧹 E-commerce CSV Cleaning (NEW!)

Have messy order data from your store? The app now auto-cleans e-commerce CSVs!

**Handles:**
- ✅ Arabic numerals in phone numbers (٠٥٠٧٨٨٩٣٨٧ → +966507889387)
- ✅ Various phone formats (spaces, dashes, country codes)
- ✅ Mixed Arabic and English names
- ✅ Automatic validation and removal of invalid numbers

**How to use:**
1. In the Streamlit app, select **"E-commerce Orders (auto-clean)"**
2. Upload your order CSV (expected format: OrderDate, empty, name, phone, address, ...)
3. The app automatically cleans and validates all data
4. Send bulk messages to your customers!

**Command-line option:**
```bash
python clean_order_csv.py "your_orders.csv"
```

See the [CSV Cleaning Guide](CSV_CLEANING_GUIDE.md) for detailed documentation.

### 🧪 Test Before Bulk Sending (NEW!)

Before sending to hundreds of contacts, always test first!

**How to test:**
1. In the **Bulk Messaging** tab, expand the **"Send Test Message to One Number"** section
2. Enter your own phone number (or any test number)
3. Write a test message (you can use {name} variables)
4. Optionally attach media to test image/video sending
5. Click **"Send Test Message"**
6. Check your WhatsApp to verify it works!

**Why test first:**
- ✅ Verify your message looks good
- ✅ Test media attachments
- ✅ Check variables are working ({name}, etc.)
- ✅ Confirm formatting and emojis render correctly
- ✅ Make sure you're logged in and connected

**Pro tip:** Send the test to your own number so you can see exactly what your customers will receive!

### UI Screenshots

The Streamlit UI includes:
1. **Sidebar Configuration**: Set API keys, country codes, delays, and login status
2. **Bulk Messaging Tab**:
   - Test message section (send to one number first)
   - CSV upload (standard or e-commerce format)
   - Message composer with variables
   - Media attachments
   - Real-time bulk sending with progress
3. **AI Auto-Responder Tab**: Select contacts to monitor and view live conversations
4. **Analytics Tab**: View detailed statistics and success rates
5. **Help Tab**: Complete documentation within the app

## 🚀 Quick Start (Command Line)

### 1. Installation

```bash
# Clone or download the repository
cd wtsp_retarget

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file with your OpenAI API key:

```bash
cp .env.example .env
```

Edit `.env` and add your API key:
```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

Get your API key from: https://platform.openai.com/api-keys

### 3. Edit Test Script

Edit `test_bot.py` to configure:
- **CONTACTS**: List of phone numbers to send to
- **MESSAGE**: Your message text
- **MEDIA_FILE**: Optional path to video/image (or None for text-only)
- **SYSTEM_PROMPT**: Customize AI behavior for your business

```python
CONTACTS = [
    "+966501234567",  # Saudi number
    "+33612345678",   # French number
    # Add more...
]

MESSAGE = """🔥 50% Discount ends today! 🔥
Don't miss out!"""

MEDIA_FILE = "/path/to/promotional_video.mp4"  # or None
```

### 4. Run

```bash
python test_bot.py
```

**First run only**: Scan QR code to login. Session is saved for future runs.

## 📖 Usage Guide

### Basic Usage

```python
from whatsapp_bot import WhatsAppBot

# Initialize
bot = WhatsAppBot()

# Send text message
bot.send_message(
    phone="+966501234567",
    message="Hello! How can I help you?"
)

# Send message with image/video
bot.send_message(
    phone="+966501234567",
    message="Check out our new product! 🔥",
    media_path="/path/to/image.jpg"
)

# Start monitoring for responses (AI auto-reply)
bot.monitor_and_respond(check_interval=10)

# Close when done
bot.close()
```

### Custom AI Prompt

```python
custom_prompt = """You are a customer service rep for XYZ Company.
Respond professionally in the customer's language.
Our products: Product A ($50), Product B ($100).
Shipping: 3-5 days within Saudi Arabia."""

bot = WhatsAppBot(system_prompt=custom_prompt)
```

### Manual Response Generation

```python
# Generate AI response without auto-sending
customer_message = "What are your prices?"
response = bot.generate_ai_response(customer_message, phone="+966501234567")
print(response)
```

## 📋 Phone Number Format

The bot accepts various phone number formats:

- ✅ `+966501234567` (international format - recommended)
- ✅ `966501234567` (without +)
- ✅ `0501234567` (Saudi local format)
- ✅ `501234567` (without leading 0)

All formats are automatically converted to the correct format.

## 🎯 Use Cases

### 1. Saudi Customer Retargeting

Send promotional messages to Saudi customers from any WhatsApp account:

```python
CONTACTS = ["+966501111111", "+966502222222", ...]
MESSAGE = "🔥 خصم 50% على منتجاتنا! 🔥"
MEDIA_FILE = "promotional_video.mp4"
```

### 2. Automated Customer Service

Monitor and respond to customer inquiries automatically:

```python
bot = WhatsAppBot(system_prompt="You are a helpful support agent...")
bot.monitor_and_respond(check_interval=10)  # Check every 10 seconds
```

### 3. Bulk Announcements

Send announcements without AI responses:

```python
bot = WhatsAppBot()  # No AI needed

for contact in contacts:
    bot.send_message(contact, "Important announcement: ...")
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Required for AI responses
OPENAI_API_KEY=sk-your-api-key

# Optional: Custom AI model (default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini  # or gpt-3.5-turbo (cheaper)
```

### Bot Options

```python
bot = WhatsAppBot(
    openai_api_key="sk-...",      # Or use .env
    system_prompt="Custom prompt",
    headless=False                # True for no browser window
)
```

### Monitoring Options

```python
bot.monitor_and_respond(
    check_interval=10,   # Seconds between checks
    duration=3600        # Optional: stop after 1 hour (None = forever)
)
```

## 🔧 Troubleshooting

### ChromeDriver Issues

**Error**: ChromeDriver version mismatch

**Solution**: The bot auto-installs the correct ChromeDriver using `webdriver-manager`. If issues persist:

```bash
pip install --upgrade webdriver-manager
```

### WhatsApp Login Issues

**Problem**: QR code not appearing or login fails

**Solutions**:
1. Delete `whatsapp_profile/` folder and re-login
2. Clear browser cache
3. Try a different Chrome version
4. Ensure Chrome is installed

### OpenAI API Errors

**Error**: API key not working

**Solutions**:
1. Verify key is correct in `.env` file
2. Check you have API credits: https://platform.openai.com/usage
3. Ensure key starts with `sk-`

### Message Not Sending

**Issue**: Messages fail to send

**Checks**:
1. Phone number is valid and registered on WhatsApp
2. You're logged into WhatsApp Web
3. Internet connection is stable
4. Contact hasn't blocked you

### Selectors Not Working

**Issue**: WhatsApp Web UI changed

**Solution**: WhatsApp occasionally updates their UI. If selectors break:
1. Check for updates to this script
2. Open an issue on GitHub with details
3. Inspect WhatsApp Web HTML to find new selectors

## 📊 Statistics

Get bot statistics:

```python
stats = bot.get_stats()
print(stats)
# {
#     'messages_sent': 10,
#     'ai_responses_sent': 5,
#     'conversations': 3,
#     'monitored_contacts': 5
# }
```

## 🔒 Security & Privacy

### API Key Security (IMPORTANT!)

- **✅ DO:** Store API keys in `.env` file
- **✅ DO:** Use environment variables for deployment
- **❌ DON'T:** Hardcode API keys in code
- **❌ DON'T:** Commit `.env` file to Git (already in .gitignore)
- **❌ DON'T:** Enter API keys in web UI when deployed publicly

**For Streamlit App:**
- The app automatically loads `OPENAI_API_KEY` from `.env` file
- If API key is in environment, it won't show input field
- If no .env found, shows input (for local testing only)
- **Always use .env file for production/deployment!**

### Data Privacy

- **API Keys**: Stored in `.env` (not committed to git)
- **Session Data**: Stored locally in `whatsapp_profile/` (not uploaded)
- **Conversations**: Stored in memory only (not persisted to disk)
- **Data Sharing**: No data sent anywhere except OpenAI API for responses
- **Uploaded CSVs**: Processed locally, not stored permanently

### Deployment

For production deployment with proper security:
- 📖 **See [DEPLOYMENT.md](DEPLOYMENT.md)** for complete guide
- Includes: Docker, VPS, Streamlit Cloud, HTTPS, password protection
- Security checklist and best practices
- Never expose API keys in deployed applications!

## ⚠️ Important Notes

### Rate Limiting

WhatsApp may rate limit or ban accounts that:
- Send too many messages too quickly
- Send spam or unsolicited messages
- Use automation excessively

**Recommendations**:
- Wait 5-10 seconds between messages
- Don't send more than 40-50 messages per day
- Only message people who consented to receive messages
- Use a business phone number, not personal

### Legal Considerations

- Only send messages to people who opted in
- Comply with local regulations (GDPR, etc.)
- Don't send spam or harassment
- Include opt-out instructions

### WhatsApp Terms of Service

Using automation may violate WhatsApp's Terms of Service. Use at your own risk.
This tool is for educational and authorized business use only.

## 🆘 Support

### Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run test
python test_bot.py

# Check if Chrome is installed
google-chrome --version   # Linux
chrome --version          # Mac
```

### Getting Help

If you encounter issues:
1. Check the Troubleshooting section above
2. Ensure all dependencies are installed
3. Verify your `.env` configuration
4. Check Python version (3.8+ required)

## 📝 License

This project is for educational and authorized business use only.
Use responsibly and in compliance with WhatsApp's Terms of Service.

## 🎓 Architecture

### File Structure

```
wtsp_retarget/
├── streamlit_app.py         # Web UI application
├── whatsapp_bot.py          # Main bot class
├── clean_order_csv.py       # E-commerce CSV cleaner
├── test_phone_cleaning.py   # Tests for cleaning functions
├── test_bot.py              # Example usage script
├── contacts_template.csv    # Sample CSV template
├── README.md                # Main documentation (this file)
├── CSV_CLEANING_GUIDE.md    # CSV cleaning documentation
├── DEPLOYMENT.md            # Production deployment guide (NEW)
├── requirements.txt         # Python dependencies
├── .env                     # API keys (create from .env.example)
├── .env.example            # Template for .env
├── whatsapp_profile/       # Browser session (auto-created)
└── temp_media/             # Temporary media uploads (auto-created)
```

### How It Works

1. **Browser Automation**: Uses Selenium to control Chrome/WhatsApp Web
2. **Session Management**: Saves browser profile to avoid repeated QR scans
3. **Message Sending**: Automates typing and sending messages with media
4. **Message Monitoring**: Periodically checks contacts for new messages
5. **AI Responses**: Uses OpenAI API to generate contextual responses
6. **Conversation Tracking**: Maintains chat history per contact

### Compared to Old Version

**Old version problems**:
- 1400+ lines of complex code
- Outdated selectors (WhatsApp UI changed)
- No ChromeDriver auto-management
- Overly complex fallback logic
- Hard to maintain and debug

**New version improvements**:
- ✅ 500 lines of clean, maintainable code
- ✅ Modern CSS selectors (more stable)
- ✅ Auto-installs correct ChromeDriver
- ✅ Simplified logic, better error handling
- ✅ Easy to understand and modify

## 🚀 Advanced Usage

### Custom Message Per Contact

```python
contacts_messages = [
    ("+966501234567", "Hello Ahmed! Special offer for you..."),
    ("+966502345678", "Hi Sara! Check out our new product..."),
]

for phone, message in contacts_messages:
    bot.send_message(phone, message)
```

### Conditional AI Responses

```python
def custom_monitor():
    for phone in bot.monitored_contacts:
        new_msg = bot.get_new_messages(phone)
        if new_msg:
            # Only respond to questions
            if "?" in new_msg:
                response = bot.generate_ai_response(new_msg, phone)
                bot.send_message(phone, response)
```

### Bulk Send from CSV

```python
import pandas as pd

# Read contacts from CSV
df = pd.read_csv("contacts.csv")

for _, row in df.iterrows():
    phone = row['phone']
    name = row['name']
    message = f"Hello {name}! Special offer just for you..."

    bot.send_message(phone, message)
```

## 🎉 Success Tips

1. **Test First**: Send to your own number first to verify everything works
2. **Start Small**: Begin with 5-10 contacts, then scale up
3. **Monitor Actively**: Watch the first few sends to catch issues early
4. **Customize AI**: Tailor the system prompt to your business
5. **Be Patient**: Wait between messages to avoid rate limits

---

Built with ❤️ for automated customer engagement
