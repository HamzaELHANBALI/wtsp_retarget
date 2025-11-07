"""
Test script for WhatsApp Bot
Demonstrates sending messages and AI auto-responses
"""

from whatsapp_bot import WhatsAppBot
import os
from pathlib import Path

# Configuration
CONTACTS = [
    "+33631055810",      # Add your test numbers here
    "+212628223573",
    # Add more contacts as needed
]

# Message to send
MESSAGE = """🔥 خصم 50% على Tiger Balm ينتهي اليوم! 🔥

لا تفوتوا هذه الفرصة الرائعة!
تأكدوا من طلبكم الآن قبل فوات الأوان!"""

# Optional: Media file path
# Set to None for text-only, or provide path to image/video
MEDIA_FILE = "/Users/hamzaelhanbali/Desktop/personal/tiger/hamza_tiger_27_octobre_1.mp4"  # Update this path

# AI System Prompt (customize for your business)
SYSTEM_PROMPT = """You are a helpful customer service representative for a business selling Tiger Balm.
You communicate professionally in both Arabic and English.
Respond in the customer's language.
Be helpful, friendly, and concise.
You can answer questions about products, prices, shipping, and promotions."""


def main():
    """Main test function"""

    print("="*60)
    print("WhatsApp Bulk Messaging Bot - Test")
    print("="*60)
    print(f"\n📋 Configuration:")
    print(f"   Contacts: {len(CONTACTS)}")
    print(f"   Media: {'Yes' if MEDIA_FILE else 'No'}")
    print(f"   AI: Enabled (if API key configured)")
    print("\n" + "="*60 + "\n")

    # Initialize bot
    try:
        bot = WhatsAppBot(system_prompt=SYSTEM_PROMPT)
    except Exception as e:
        print(f"❌ Failed to initialize bot: {e}")
        return

    try:
        # Step 1: Send messages to all contacts
        print("📤 STEP 1: Sending messages to contacts\n")

        for i, contact in enumerate(CONTACTS, 1):
            print(f"[{i}/{len(CONTACTS)}] Sending to {contact}...")

            success = bot.send_message(
                phone=contact,
                message=MESSAGE,
                media_path=MEDIA_FILE
            )

            if success:
                print(f"   ✅ Sent successfully")
            else:
                print(f"   ❌ Failed")

            # Wait between messages (except for last one)
            if i < len(CONTACTS):
                import time
                wait_time = 5
                print(f"   ⏳ Waiting {wait_time}s before next send...\n")
                time.sleep(wait_time)

        print("\n" + "="*60)
        print("✅ All messages sent!")
        print("="*60)

        # Step 2: Start monitoring for responses
        print("\n📤 STEP 2: Starting AI monitoring\n")
        print("The bot will now:")
        print("   - Check for incoming messages every 10 seconds")
        print("   - Automatically respond using AI")
        print("   - Maintain conversation context per contact")
        print("\n   Press Ctrl+C to stop monitoring\n")
        print("="*60 + "\n")

        # Monitor indefinitely (or set duration in seconds)
        bot.monitor_and_respond(
            check_interval=10,    # Check every 10 seconds
            duration=None         # None = run forever, or set seconds
        )

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        bot.close()
        print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
