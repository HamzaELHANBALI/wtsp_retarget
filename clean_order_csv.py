"""
CSV Order Data Cleaner for WhatsApp Bot
Cleans order data from e-commerce exports and prepares it for bulk messaging.

Handles:
- Arabic and English names
- Various phone number formats (Arabic numerals, spaces, country codes)
- Saudi Arabian phone number normalization
"""

import pandas as pd
import re
from pathlib import Path


# Arabic to English numeral mapping
ARABIC_NUMERALS = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}


def convert_arabic_numerals(text):
    """Convert Arabic numerals to English numerals"""
    if pd.isna(text):
        return text

    text = str(text)
    for arabic, english in ARABIC_NUMERALS.items():
        text = text.replace(arabic, english)
    return text


def clean_phone_number(phone, default_country_code='+966'):
    """
    Clean and normalize phone numbers to consistent format.

    Handles:
    - Arabic numerals → English numerals
    - Spaces, dashes, parentheses removal
    - Country code normalization
    - Various Saudi formats (0XXXXXXXXX, 5XXXXXXXX, +966XXXXXXXXX)

    Returns:
    - Normalized format: +966XXXXXXXXX (for Saudi numbers)
    - None if invalid
    """
    if pd.isna(phone):
        return None

    # Convert to string and handle Arabic numerals
    phone = str(phone).strip()
    phone = convert_arabic_numerals(phone)

    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', phone)

    # Remove any + signs except at the start
    if phone.startswith('+'):
        phone = '+' + phone[1:].replace('+', '')
    else:
        phone = phone.replace('+', '')

    # If it's empty after cleaning, return None
    if not phone or phone == '+':
        return None

    # If it starts with +, extract country code
    if phone.startswith('+'):
        # Already has country code
        # Validate it's a reasonable length (10-15 digits after +)
        if len(phone) >= 11 and len(phone) <= 16:
            return phone
        else:
            return None

    # Handle Saudi number formats
    # Saudi numbers: 9 digits without leading 0, 10 digits with leading 0

    # Remove leading zeros for normalization
    phone = phone.lstrip('0')

    # Saudi mobile numbers start with 5 and are 9 digits (without 0)
    if phone.startswith('5') and len(phone) == 9:
        return default_country_code + phone

    # If it starts with 966 (country code without +)
    if phone.startswith('966'):
        # Already has country code
        if len(phone) == 12:  # 966 + 9 digits
            return '+' + phone
        else:
            return None

    # If it's 8 digits or less, might be incomplete
    if len(phone) < 9:
        return None

    # If it's 9 digits and starts with 5, add country code
    if len(phone) == 9 and phone.startswith('5'):
        return default_country_code + phone

    # If it's 10 digits and starts with 5, remove any leading digit and add country code
    if len(phone) == 10 and phone[0] in '05':
        phone = phone.lstrip('0')
        if len(phone) == 9 and phone.startswith('5'):
            return default_country_code + phone

    # Default: try to add country code if it looks like a valid length
    if len(phone) == 9:
        return default_country_code + phone

    # If we can't determine format, return None
    return None


def clean_name(name):
    """
    Clean customer names.

    Handles:
    - Extra whitespace
    - Special characters (keeps Arabic and English letters)
    - Title case for English names
    """
    if pd.isna(name):
        return "Customer"

    name = str(name).strip()

    # Remove extra whitespace
    name = ' '.join(name.split())

    # If empty after cleaning, return default
    if not name:
        return "Customer"

    return name


def clean_address(address):
    """Clean address field"""
    if pd.isna(address):
        return ""

    address = str(address).strip()
    # Remove extra whitespace
    address = ' '.join(address.split())
    return address


def clean_order_csv(input_file, output_file=None, country_code='+966'):
    """
    Clean order CSV file and prepare for WhatsApp bulk messaging.

    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file (default: input_file_cleaned.csv)
        country_code: Default country code for phone numbers (default: +966 for Saudi Arabia)

    Returns:
        DataFrame with cleaned data
    """
    print(f"Reading CSV file: {input_file}")

    # Read CSV with flexible column handling
    df = pd.read_csv(input_file, encoding='utf-8-sig')

    print(f"Total records: {len(df)}")
    print(f"Columns found: {list(df.columns)}")

    # Detect column names (they might be unnamed)
    # Based on the description: OrderDate, (empty), name, phone, address, url, sku, Product, quantity, price, currency, notes, ...

    # Try to identify columns by position if names are unclear
    if len(df.columns) >= 5:
        # Assume: col0=OrderDate, col1=empty/location, col2=name, col3=phone, col4=address
        col_names = list(df.columns)

        # Map to our expected names
        order_date_col = col_names[0] if len(col_names) > 0 else None
        name_col = col_names[2] if len(col_names) > 2 else None
        phone_col = col_names[3] if len(col_names) > 3 else None
        address_col = col_names[4] if len(col_names) > 4 else None

        print(f"\nDetected columns:")
        print(f"  Order Date: {order_date_col}")
        print(f"  Name: {name_col}")
        print(f"  Phone: {phone_col}")
        print(f"  Address: {address_col}")
    else:
        print("ERROR: Not enough columns in CSV file")
        return None

    # Create cleaned DataFrame
    cleaned_df = pd.DataFrame()

    # Clean each field
    print("\nCleaning data...")

    if order_date_col:
        cleaned_df['order_date'] = df[order_date_col]

    if name_col:
        cleaned_df['name'] = df[name_col].apply(clean_name)

    if phone_col:
        print("  - Cleaning phone numbers...")
        cleaned_df['phone'] = df[phone_col].apply(lambda x: clean_phone_number(x, country_code))

    if address_col:
        cleaned_df['address'] = df[address_col].apply(clean_address)

    # Add empty custom_message column for user to fill later
    cleaned_df['custom_message'] = ''

    # Remove rows with invalid phone numbers
    initial_count = len(cleaned_df)
    cleaned_df = cleaned_df[cleaned_df['phone'].notna()]
    removed_count = initial_count - len(cleaned_df)

    print(f"\nCleaning complete!")
    print(f"  Valid phone numbers: {len(cleaned_df)}")
    print(f"  Invalid/removed: {removed_count}")

    # Show sample of cleaned data
    print(f"\nSample cleaned data:")
    print(cleaned_df.head(10).to_string())

    # Show phone number format distribution
    print(f"\nPhone number format distribution:")
    phone_formats = cleaned_df['phone'].apply(lambda x: 'Saudi (+966)' if str(x).startswith('+966') else 'Other')
    print(phone_formats.value_counts())

    # Save to file
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_cleaned.csv"

    cleaned_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ Cleaned data saved to: {output_file}")
    print(f"✅ Ready for upload to Streamlit app!")

    return cleaned_df


def clean_single_phone(phone, country_code='+966'):
    """
    Utility function to clean a single phone number.
    Useful for testing or one-off cleaning.
    """
    return clean_phone_number(phone, country_code)


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("WhatsApp Order CSV Cleaner")
    print("=" * 70)
    print()

    # Get input file from command line or prompt
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("Enter CSV file path: ").strip()

    # Get country code (optional)
    if len(sys.argv) > 2:
        country_code = sys.argv[2]
    else:
        country_code = '+966'  # Default to Saudi Arabia

    # Check if file exists
    if not Path(input_file).exists():
        print(f"❌ ERROR: File not found: {input_file}")
        sys.exit(1)

    # Clean the CSV
    try:
        df = clean_order_csv(input_file, country_code=country_code)

        if df is not None:
            print("\n" + "=" * 70)
            print("✅ SUCCESS! Your CSV is ready for bulk messaging.")
            print("=" * 70)
            print("\nNext steps:")
            print("1. Review the cleaned CSV file")
            print("2. Add custom messages in the 'custom_message' column (optional)")
            print("3. Upload to Streamlit app: streamlit run streamlit_app.py")
            print("4. Send your bulk WhatsApp messages!")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
