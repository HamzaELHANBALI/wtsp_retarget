"""
Test script to send WhatsApp messages to multiple numbers
From: Your French WhatsApp number
To: Multiple contacts (test with your brother and others)

This script logs in ONCE and sends to multiple numbers without relogging.
"""

from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter

# Initialize the retargeter
# Works with ANY WhatsApp number - your French number is perfect!
# This will log in ONCE and keep the session open
retargeter = SaudiWhatsAppRetargeter(
    daily_limit=40  # Maximum messages per day
)

# Test contacts - Add multiple phone numbers here
# Format: +212XXXXXXXXX (Morocco) or +966XXXXXXXXX (Saudi) or any country code
test_contacts = [
    "+212628223573",  # Your brother in Morocco
    "+33631055810"    # Wife
]

# Test message
test_message = """السلام عليكم ورحمة الله وبركاته

هذه رسالة تجريبية من البوت.

Test message from the bot.

شكراً"""

# Or use a simple message:
# test_message = "Hello! This is a test message from the WhatsApp bot. السلام عليكم"

print("=" * 60)
print("WhatsApp Bulk Message Test")
print("=" * 60)
print("\nInstructions:")
print("1. Chrome browser will open automatically")
print("2. WhatsApp Web will load")
print("3. Scan the QR code with your FRENCH WhatsApp")
print("4. Script will auto-detect when you're logged in")
print("5. Script will send messages to ALL contacts below")
print("6. You will ONLY log in ONCE - session stays open!")
print(f"\nSending to {len(test_contacts)} contact(s):")
for i, contact in enumerate(test_contacts, 1):
    print(f"  {i}. {contact}")
print(f"\nMessage: {test_message[:50]}...")
print("\n" + "=" * 60 + "\n")

try:
    # Send bulk messages - this will send to all contacts in one session
    retargeter.send_bulk_messages(
        contacts_list=test_contacts,
        message_template=test_message,
        prioritize_engaged=False
    )
    
    print("\n✅ All test messages completed!")
    print("Check the recipients' WhatsApp to confirm receipt.")
        
except Exception as e:
    print(f"\n❌ Error occurred: {str(e)}")
    print("Please check:")
    print("1. Phone numbers are correct")
    print("2. Numbers are on WhatsApp")
    print("3. You're logged into WhatsApp Web")
    print("4. Internet connection is stable")
    
finally:
    # Close the browser (only at the end)
    retargeter.close()
    print("\nTest completed. Browser closed.")

