# AI-Powered WhatsApp Auto-Response Setup

## Overview

This enhanced version adds OpenAI API integration to automatically respond to customer messages.

## Features

✅ **Automatic Responses**: AI-powered responses to customer messages  
✅ **Conversation History**: Maintains context across messages  
✅ **Multi-language**: Responds in Arabic and English  
✅ **Background Monitoring**: Monitors messages in the background  
✅ **Customizable**: Custom system prompts for your business  

## Setup

### 1. Install Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

This will install:
- selenium
- pandas
- openai

### 2. Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key

### 3. Set API Key

**Option 1: Environment Variable (Recommended)**
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

**Option 2: In the Script**
Edit `test_with_ai.py`:
```python
OPENAI_API_KEY = "sk-your-api-key-here"
```

## Usage

### Basic Usage

```python
from whatsapp_retarget_with_ai import SaudiWhatsAppRetargeterWithAI

# Initialize with AI
retargeter = SaudiWhatsAppRetargeterWithAI(
    daily_limit=40,
    openai_api_key="sk-your-api-key-here"
)

# Send initial messages
contacts = ["+212628223573", "+966501111111"]
for contact in contacts:
    retargeter.send_message_to_contact(contact, "Hello!")

# Start monitoring for responses
retargeter.start_monitoring(check_interval=10)  # Check every 10 seconds

# Keep running
import time
while True:
    time.sleep(1)
```

### Custom System Prompt

```python
SYSTEM_PROMPT = """You are a helpful customer service representative for a business targeting Saudi Arabia customers.
You communicate in Arabic and English. Be professional, friendly, and helpful.
Always respond in a way that matches the customer's language preference.
Keep responses concise and helpful."""

retargeter = SaudiWhatsAppRetargeterWithAI(
    daily_limit=40,
    openai_api_key="sk-your-api-key-here",
    system_prompt=SYSTEM_PROMPT
)
```

## How It Works

1. **Send Initial Messages**: Send messages to your contacts
2. **Monitor Incoming**: Script checks for new messages every 10 seconds (configurable)
3. **Generate Response**: When a customer responds, AI generates a response
4. **Send Reply**: Automatically sends the AI-generated response
5. **Maintain Context**: Keeps conversation history for better responses

## Example Flow

```
You: السلام عليكم (Initial message)
Customer: مرحبا، كيف يمكنني المساعدة؟
AI: مرحبا! كيف يمكنني مساعدتك اليوم؟
Customer: أريد معرفة المزيد عن المنتج
AI: بالطبع! سأكون سعيدًا لإخبارك بالمزيد...
```

## Configuration

### Check Interval
How often to check for new messages:
```python
retargeter.start_monitoring(check_interval=10)  # 10 seconds
```

### AI Model
Change the model in `whatsapp_retarget_with_ai.py`:
```python
model="gpt-4o-mini"  # Cheaper, faster
# or
model="gpt-4"  # More capable, more expensive
```

### Response Length
Adjust `max_tokens` in the `generate_ai_response` method:
```python
max_tokens=200  # Shorter responses
# or
max_tokens=500  # Longer responses
```

## Cost Considerations

- **gpt-4o-mini**: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- **gpt-3.5-turbo**: ~$0.50 per 1M input tokens, ~$1.50 per 1M output tokens
- **gpt-4**: ~$30 per 1M input tokens, ~$60 per 1M output tokens

For customer service, `gpt-4o-mini` is recommended (good balance of cost and quality).

## Troubleshooting

### AI Not Responding
- Check API key is set correctly
- Verify you have OpenAI credits
- Check internet connection

### Messages Not Detected
- WhatsApp Web structure may have changed
- Try adjusting the check interval
- Check browser console for errors

### Responses Not Relevant
- Customize the system prompt
- Adjust temperature (lower = more focused)
- Increase max_tokens for longer context

## Security

⚠️ **Important**: 
- Never commit your API key to git
- Use environment variables for API keys
- Monitor your OpenAI usage to avoid unexpected costs
- Set up usage limits in OpenAI dashboard

## Example Script

See `test_with_ai.py` for a complete example.

