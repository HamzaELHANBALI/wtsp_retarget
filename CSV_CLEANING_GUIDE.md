# CSV Cleaning Guide for E-commerce Orders

This guide explains how to use the CSV cleaning tools to prepare your e-commerce order data for WhatsApp bulk messaging.

## 📋 Problem Statement

E-commerce order exports often have messy data:
- **Arabic numerals** in phone numbers (٠١٢٣٤٥٦٧٨٩)
- **Inconsistent formats**: +966, 0, spaces, dashes
- **Mixed languages**: Arabic and English names
- **Extra columns**: You only need name, phone, address

This tool cleans all of that automatically!

## 🚀 Quick Start

### Option 1: Use Streamlit UI (Easiest)

1. Launch the Streamlit app:
```bash
streamlit run streamlit_app.py
```

2. In the "Bulk Messaging" tab:
   - Select **"E-commerce Orders (auto-clean)"**
   - Upload your CSV file
   - The app will automatically:
     - Convert Arabic numerals to English
     - Normalize all phone numbers to +966XXXXXXXXX format
     - Clean names
     - Remove invalid records

3. Review the cleaned data and send messages!

### Option 2: Command Line Tool

Clean your CSV file before uploading:

```bash
python clean_order_csv.py "KECHDISCOUNTS_-_Youcan-Orders.csv"
```

This creates a file named `KECHDISCOUNTS_-_Youcan-Orders_cleaned.csv` ready for upload.

## 📊 Expected CSV Format

Your e-commerce CSV should have columns in this order:

| Position | Column Name | Description | Required |
|----------|-------------|-------------|----------|
| 0 | OrderDate | Date/time of order | ❌ Optional |
| 1 | (empty) | Sometimes location info | ❌ Optional |
| 2 | name | Customer name (Arabic/English) | ✅ Required |
| 3 | phone | Phone number (any format) | ✅ Required |
| 4 | address | Delivery address/city | ❌ Optional |
| 5+ | ... | Other columns (ignored) | ❌ Optional |

**Example:**
```csv
OrderDate,,"ناصر الخالدي","٠٥٠٧٨٨٩٣٨٧","Riyadh",url,sku,Product,1,100,SAR,default
2024-01-15,,"Ahmed Abdullah","050 099 0167","Jeddah",url,sku,Product,2,200,SAR,default
```

## 🔧 Cleaning Functions

### Phone Number Cleaning

Handles all these formats:

| Input Format | Output Format | Description |
|--------------|---------------|-------------|
| `٠٥٠٧٨٨٩٣٨٧` | `+966507889387` | Arabic numerals → English |
| `050 099 0167` | `+966500990167` | Removes spaces |
| `0501234567` | `+966501234567` | Adds country code |
| `+966501234567` | `+966501234567` | Already clean ✓ |
| `966501234567` | `+966501234567` | Adds + prefix |
| `501234567` | `+966501234567` | Adds 0 and country code |

**Invalid numbers are automatically removed:**
- Too short (< 9 digits)
- Non-numeric characters (after cleaning)
- Empty values

### Name Cleaning

- Removes extra whitespace
- Handles Arabic and English names
- Sets default "Customer" if empty
- Preserves special characters

### Arabic Numeral Conversion

Automatically converts:
```
٠ → 0
١ → 1
٢ → 2
٣ → 3
٤ → 4
٥ → 5
٦ → 6
٧ → 7
٨ → 8
٩ → 9
```

## 📤 Output Format

The cleaned CSV will have these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `name` | Cleaned customer name | "ناصر الخالدي" |
| `phone` | Normalized phone (+966...) | "+966507889387" |
| `address` | City/address if available | "Riyadh" |
| `custom_message` | Empty (for you to fill) | "" |

## 💡 Usage Examples

### Example 1: Clean via Command Line

```bash
# Clean the CSV
python clean_order_csv.py "orders.csv"

# Output shows:
#   Total records: 5442
#   Valid phone numbers: 5238
#   Invalid/removed: 204
#   Saved to: orders_cleaned.csv
```

### Example 2: Custom Country Code

```bash
# For non-Saudi numbers (e.g., UAE +971)
python clean_order_csv.py "orders.csv" "+971"
```

### Example 3: Use in Streamlit

1. Open Streamlit app
2. Select "E-commerce Orders (auto-clean)"
3. Upload CSV
4. See instant preview of cleaned data
5. Download cleaned version or send directly

## 🧪 Testing

Test the cleaning functions:

```bash
python test_phone_cleaning.py
```

This runs comprehensive tests on:
- Arabic numeral conversion
- Phone number normalization
- Name cleaning
- Edge cases (empty, invalid, etc.)

## 🔍 Troubleshooting

### Problem: "Not enough columns in CSV file"

**Solution:** Your CSV doesn't match the expected format. Make sure it has at least 5 columns with name in column 3 and phone in column 4.

### Problem: Too many invalid phone numbers

**Causes:**
- Phone column is in a different position
- Numbers are in a non-standard format

**Solution:**
1. Open your CSV in Excel/Google Sheets
2. Check which column contains phone numbers
3. Manually adjust column positions if needed
4. Or contact support

### Problem: Names not displaying correctly

**Solution:** Make sure your CSV is saved with UTF-8 encoding to support Arabic characters.

In Excel:
- Save As → CSV UTF-8 (Comma delimited)

In Google Sheets:
- File → Download → Comma Separated Values (.csv)

## 📊 Statistics After Cleaning

The tool shows you:

| Metric | Description |
|--------|-------------|
| **Total Records** | Original count from CSV |
| **Valid Contacts** | After cleaning and validation |
| **Invalid/Removed** | Phone numbers that couldn't be fixed |
| **Success Rate** | % of valid numbers |

**Example Output:**
```
✅ Cleaned 5442 records → 5238 valid contacts
📍 Removed 204 records with invalid phone numbers
```

## 🎯 Best Practices

1. **Always review cleaned data** before sending bulk messages
2. **Test with a small batch first** (10-20 contacts)
3. **Check for duplicates** - one person might have multiple orders
4. **Segment by city/address** for targeted messaging
5. **Personalize messages** using {name} and {custom_message}

## 🔐 Privacy & Data Handling

- **No data is uploaded** to external servers
- **All cleaning happens locally** on your computer
- **Original CSV is never modified** - a new file is created
- **API keys stay on your machine** (in .env or session state)

## 📝 Code Usage

If you want to use the cleaning functions in your own code:

```python
from clean_order_csv import clean_phone_number, clean_name, convert_arabic_numerals

# Clean a single phone number
phone = clean_phone_number("٠٥٠٧٨٨٩٣٨٧", "+966")
# Returns: "+966507889387"

# Clean a name
name = clean_name("  Ahmed  ")
# Returns: "Ahmed"

# Convert Arabic numerals
text = convert_arabic_numerals("Order ١٢٣٤")
# Returns: "Order 1234"
```

## 🆘 Support

If you encounter issues:

1. Check this guide first
2. Run `python test_phone_cleaning.py` to verify installation
3. Try the sample CSV template from the Streamlit app
4. Check the README.md for general troubleshooting

## 📚 Related Documentation

- [Main README](README.md) - Complete bot documentation
- [Streamlit UI Guide](README.md#-new-streamlit-web-ui) - UI features
- [WhatsApp Bot API](whatsapp_bot.py) - Core bot functionality

---

**Happy Messaging! 📱💬**
