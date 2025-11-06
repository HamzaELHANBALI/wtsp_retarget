"""
Test script with AI-powered automatic responses
From: Your French WhatsApp number
To: Multiple contacts with AI auto-responses

This script:
1. Sends messages to multiple contacts
2. Monitors for incoming messages
3. Automatically responds using OpenAI API
"""

from whatsapp_retarget_with_ai import SaudiWhatsAppRetargeterWithAI
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from .env file
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not OPENAI_API_KEY:
    print("⚠️  Warning: OPENAI_API_KEY not found in .env file")
    print("   Please add your API key to .env file:")
    print("   OPENAI_API_KEY=sk-your-api-key-here")
    exit(1)

# Custom system prompt (optional)
SYSTEM_PROMPT = """You are a helpful customer service representative for a business targeting Saudi Arabia customers.
You communicate in Arabic and English. Be professional, friendly, and helpful.
Always respond in a way that matches the customer's language preference.
Keep responses concise and helpful."""

# Initialize the retargeter with AI
retargeter = SaudiWhatsAppRetargeterWithAI(
    daily_limit=40,
    openai_api_key=OPENAI_API_KEY,
    system_prompt=SYSTEM_PROMPT
)

# Test contacts - Add multiple numbers here
test_contacts = [
    "+33631055810",
    "+212628223573"
]

# Initial message to send (will be used as caption if media is provided)
initial_message = """🔥 خصم 50% على Tiger Balm ينتهي اليوم! 🔥

لا تفوتوا هذه الفرصة الرائعة!
تأكدوا من طلبكم الآن قبل فوات الأوان!"""

# Optional: Add video/image file path
# Example: media_file = "/path/to/your/video.mp4"
# Or: media_file = "/path/to/your/image.jpg"
media_file = "/Users/hamzaelhanbali/Desktop/personal/tiger/hamza_tiger_27_octobre_1.mp4"  # Set to None for text-only, or provide file path for media

print("=" * 60)
print("WhatsApp Bulk Messaging with AI Auto-Responses")
print("=" * 60)
print("\nFeatures:")
print("1. Send bulk messages to multiple contacts")
print("2. Monitor incoming messages automatically")
print("3. AI-powered automatic responses")
print("4. Conversation history maintained per contact")
print(f"\n📋 Test Contacts ({len(test_contacts)} contact(s)):")
for i, contact in enumerate(test_contacts, 1):
    print(f"   {i}. {contact}")
print("\n" + "=" * 60 + "\n")

try:
    # Send initial messages to all contacts
    print("📤 Sending initial messages to all contacts...")
    print(f"   Total contacts: {len(test_contacts)}\n")
    
    for i, contact in enumerate(test_contacts, 1):
        print(f"[{i}/{len(test_contacts)}] Sending to {contact}...")
        if media_file:
            print(f"   📎 Attaching media: {media_file}")
        
        if retargeter.send_message_to_contact(contact, initial_message, media_path=media_file):
            print(f"   ✅ Successfully sent to {contact}")
            retargeter.total_sent += 1
            # Add to monitoring list
            retargeter.contacts_to_monitor.append(contact)
        else:
            print(f"   ❌ Failed to send to {contact}")
        
        # Wait between sends (except for last one)
        if i < len(test_contacts):
            wait_time = 5
            print(f"   ⏳ Waiting {wait_time} seconds before next send...\n")
            time.sleep(wait_time)
    
    print("\n" + "=" * 60)
    print("✅ Initial messages sent to all contacts!")
    print("=" * 60)
    print("\n🤖 Starting AI monitoring...")
    print("   The bot will now monitor for incoming messages from ANY contact")
    print("   and respond automatically using AI.")
    print("   Each contact has separate conversation history.")
    print("   Press Ctrl+C to stop.\n")
    print("=" * 60 + "\n")
    
    # Start monitoring for incoming messages
    retargeter.start_monitoring(check_interval=10)  # Check every 10 seconds
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
        retargeter.stop_monitoring()
        
except Exception as e:
    print(f"\n❌ Error occurred: {str(e)}")
    
finally:
    retargeter.close()
    print("\n✅ Test completed!")

