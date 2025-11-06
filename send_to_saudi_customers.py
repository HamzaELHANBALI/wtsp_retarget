"""
Simple script to send WhatsApp messages to Saudi customers
using your Moroccan WhatsApp number via WhatsApp Web

Requirements:
- Moroccan WhatsApp number (or any WhatsApp number)
- CSV file with Saudi customer phone numbers
- Chrome browser + ChromeDriver installed
"""

from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter
import pandas as pd

# Initialize the retargeter
# Works with ANY WhatsApp number - your Moroccan number is perfect!
retargeter = SaudiWhatsAppRetargeter(
    daily_limit=40  # Maximum messages per day (adjust as needed)
)

# Load your CSV file with Saudi customers
# CSV should have columns: phone (or number), and optionally: name, last_contact
contacts_df = pd.read_csv('saudi_customers.csv')

# Your message template
# Use {name} for personalization if your CSV has a 'name' column
message = """السلام عليكم ورحمة الله وبركاته

عزيزي {name}،

نود أن نعلمك بعروضنا الحصرية الجديدة!

شكراً لثقتك بنا."""

# If your CSV doesn't have a 'name' column, use this simpler message:
# message = """السلام عليكم ورحمة الله وبركاته
#
# عزيزي العميل، نود أن نعلمك بعروضنا الحصرية الجديدة!
#
# شكراً لثقتك بنا."""

# Send bulk messages
try:
    print("=" * 60)
    print("Starting WhatsApp retargeting campaign")
    print("=" * 60)
    print("\nInstructions:")
    print("1. Chrome browser will open automatically")
    print("2. WhatsApp Web will load")
    print("3. Scan the QR code with your MOROCCAN WhatsApp")
    print("4. Press Enter after logging in")
    print("5. Script will start sending messages automatically\n")
    
    retargeter.send_bulk_messages(
        contacts_list=contacts_df,
        message_template=message,
        prioritize_engaged=True  # Prioritizes customers with recent contact if 'last_contact' column exists
    )
    
    print("\n✅ Campaign completed successfully!")
    
except Exception as e:
    print(f"\n❌ Error occurred: {str(e)}")
    
finally:
    # Always close the browser
    retargeter.close()

