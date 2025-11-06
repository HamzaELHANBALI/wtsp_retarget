"""
Example usage of Saudi WhatsApp Retargeter
This demonstrates how to use the combined retargeting solution
"""

from whatsapp_retarget_saudi import SaudiWhatsAppRetargeter
import pandas as pd

# Example 1: Using a simple list of phone numbers
def example_simple_list():
    # Initialize retargeter with your Saudi WhatsApp numbers
    retargeter = SaudiWhatsAppRetargeter(
        saudi_numbers=[
            '+966501234567',  # Replace with your actual WhatsApp numbers
            '+966502345678',
            '+966503456789'
        ],
        daily_limit_per_number=40  # Conservative limit per number
    )
    
    # List of Saudi phone numbers to retarget
    contacts = [
        '+966501111111',
        '+966502222222',
        '+966503333333',
    ]
    
    # Message template (supports Arabic and English)
    message = """السلام عليكم ورحمة الله وبركاته

عزيزي العميل، نود أن نعلمك بعروضنا الحصرية الجديدة!

شكراً لثقتك بنا."""
    
    try:
        retargeter.send_bulk_messages(
            contacts_list=contacts,
            message_template=message,
            prioritize_engaged=False
        )
    finally:
        retargeter.close()


# Example 2: Using a CSV file with customer data
def example_csv_file():
    # Load customer data from CSV
    # CSV should have columns: phone, name (optional), last_contact (optional)
    customers_df = pd.read_csv('saudi_customers.csv')
    
    # Initialize retargeter
    retargeter = SaudiWhatsAppRetargeter(
        saudi_numbers=[
            '+966501234567',
            '+966502345678',
            '+966503456789'
        ],
        daily_limit_per_number=40
    )
    
    # Personalized message template
    message = """السلام عليكم {name}

نود أن نعلمك بعروضنا الحصرية الجديدة!

شكراً لثقتك بنا."""
    
    try:
        retargeter.send_bulk_messages(
            contacts_list=customers_df,
            message_template=message,
            prioritize_engaged=True  # Will prioritize by last_contact if available
        )
    finally:
        retargeter.close()


# Example 3: English message for bilingual customers
def example_english_message():
    retargeter = SaudiWhatsAppRetargeter(
        saudi_numbers=[
            '+966501234567',
            '+966502345678',
            '+966503456789'
        ],
        daily_limit_per_number=40
    )
    
    contacts = [
        '+966501111111',
        '+966502222222',
    ]
    
    message = """Assalamu Alaikum

Dear Valued Customer,

We're excited to share our exclusive new offers with you!

Thank you for your trust."""
    
    try:
        retargeter.send_bulk_messages(
            contacts_list=contacts,
            message_template=message,
            prioritize_engaged=False
        )
    finally:
        retargeter.close()


if __name__ == "__main__":
    # Run the example you want
    print("Choose an example:")
    print("1. Simple list of contacts")
    print("2. CSV file with customer data")
    print("3. English message")
    
    choice = input("Enter choice (1-3): ")
    
    if choice == "1":
        example_simple_list()
    elif choice == "2":
        example_csv_file()
    elif choice == "3":
        example_english_message()
    else:
        print("Invalid choice")

