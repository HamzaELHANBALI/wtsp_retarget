# Categorized Clients Lists

This folder contains categorized client lists extracted from `KECHDISCOUNTS - Youcan-Orders.csv`.

## Files

### 1. Women Clients Files

#### `women_clients_full_list.csv`
- **Description**: Complete list of ALL female clients (744 unique clients)
- **Columns**: name, phone, address, order_date, product
- **Total**: 744 unique women (by phone number)

#### `women_clients_part_XX_of_15.csv` (15 files)
- **Description**: Women clients split into manageable chunks of 50 clients each
- **Files**: 15 files total
  - Parts 01-14: 50 clients each
  - Part 15: 44 clients (remaining)
- **Columns**: name, phone, address, order_date, product
- **Purpose**: Easier to manage and send messages in batches

#### `women_clients_200.csv` (Legacy)
- **Description**: First 200 female clients (kept for backward compatibility)
- **Note**: Use the full list or parts instead

**Filtering criteria for all women files**:
  - Names ending with "ة" (ta marbuta)
  - Names starting with "أم" or "ام" (Umm - mother of)
  - Common Arabic female names (ريم، مريم، فاطمة، نور، etc.)
  - Unique phone numbers only (no duplicates)

### 2. `wooden_cigarette_holder_clients.csv`
- **Description**: Clients who purchased "Wooden Electric Cigarette Holder"
- **Columns**: name, phone, address, order_date, product
- **Total**: 194 unique clients
- **Note**: Only includes clients with unique phone numbers (duplicates removed)

## Usage

These CSV files can be used with the WhatsApp Bulk Messaging Bot:

1. **Load in Streamlit App**:
   - Go to "Bulk Messaging" tab
   - Upload the CSV file
   - The app will automatically clean phone numbers and validate them

2. **Format**:
   - Phone numbers may need cleaning (Arabic numerals, formatting)
   - The app's CSV cleaning feature will handle this automatically
   - Required columns: `phone`, `name` (optional), `address` (optional)

## Notes

- All phone numbers are unique (duplicates removed based on phone number)
- Phone numbers may contain Arabic numerals that need conversion
- Addresses are preserved from the original order data
- Order dates and products are included for reference

## Regenerating Files

To regenerate these files or modify the categorization:

```bash
python3 categorize_clients.py
```

The script will:
1. Read from `KECHDISCOUNTS - Youcan-Orders.csv`
2. Extract 200 women clients (first 200 unique by phone)
3. Extract all clients who bought "Wooden Electric Cigarette Holder"
4. Save results to this folder

## Female Name Detection

The script uses multiple criteria to identify female names:
- Names ending with "ة" (ta marbuta)
- Names starting with "أم" or "ام"
- Common Arabic female names database
- Some names may be ambiguous (e.g., "علاء" can be both male and female)

If you need to refine the list, you can manually review and edit the CSV files.

