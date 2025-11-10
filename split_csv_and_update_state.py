#!/usr/bin/env python3
"""
Script to:
1. Split the first 400 rows of CSV into 10 files (40 rows each)
2. Update bot_state.json with first 40 contacts as contacted with follow-up sent
"""

import csv
import json
import re
from pathlib import Path
from datetime import datetime

def format_phone(phone):
    """Format phone number to standard format (+966XXXXXXXXX)"""
    if not phone:
        return None
    
    # Convert Arabic digits to Western digits
    arabic_to_western = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    phone_str = str(phone)
    for arabic, western in arabic_to_western.items():
        phone_str = phone_str.replace(arabic, western)
    
    # Remove all non-digit characters (spaces, dashes, etc.)
    phone = re.sub(r'\D', '', phone_str)
    
    # Remove leading zeros
    phone = phone.lstrip('0')
    
    # If it starts with 966, add + prefix
    if phone.startswith('966'):
        return f"+{phone}"
    # Otherwise, assume it's a Saudi number and add +966
    elif len(phone) == 9:  # 9-digit Saudi number
        return f"+966{phone}"
    elif len(phone) >= 10:
        # Might already have country code or longer number
        if phone.startswith('966'):
            return f"+{phone}"
        else:
            return f"+966{phone[-9:]}"  # Take last 9 digits and add country code
    else:
        # Too short, return as is with +966
        return f"+966{phone}"

# Read the CSV file
csv_file = Path("KECHDISCOUNTS - Youcan-Orders.csv")
clients_dir = Path("clients_list")
bot_state_file = Path("bot_state.json")

# Create clients_list directory
clients_dir.mkdir(exist_ok=True)
print(f"✅ Created directory: {clients_dir}")

# Read CSV
print(f"📖 Reading CSV file: {csv_file}")
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"   Total rows in CSV: {len(rows)}")

# Take first 400 rows
first_400 = rows[:400]
print(f"   Taking first 400 rows")

# Split into 10 files (40 rows each)
chunk_size = 40
num_files = 10

# Get header from original file
with open(csv_file, 'r', encoding='utf-8') as f:
    header = f.readline().strip()

for i in range(num_files):
    start_idx = i * chunk_size
    end_idx = min(start_idx + chunk_size, len(first_400))
    
    if start_idx >= len(first_400):
        break
    
    chunk = first_400[start_idx:end_idx]
    output_file = clients_dir / f"clients_part_{i+1:02d}.csv"
    
    # Write chunk to file
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        if chunk:
            # Write header
            fieldnames = list(chunk[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chunk)
    
    print(f"   ✅ Created {output_file.name}: {len(chunk)} rows")

print(f"\n✅ Created {num_files} files in {clients_dir}/")

# Now update bot_state.json with first 40 contacts
print(f"\n📝 Updating bot_state.json with first 40 contacts...")

# Read current bot_state.json
if bot_state_file.exists():
    with open(bot_state_file, 'r', encoding='utf-8') as f:
        bot_state = json.load(f)
else:
    bot_state = {
        "monitored_contacts": [],
        "last_contact_time": {},
        "customer_responded": {},
        "followup_sent": {},
        "seen_message_ids": {},
        "seen_message_texts": {},
        "last_saved": datetime.now().isoformat()
    }

# Get first 40 contacts
first_40 = rows[:40]
contact_time = datetime.now().isoformat()

# Process each contact
new_contacts = []
for row in first_40:
    phone = format_phone(row.get('phone', ''))
    if not phone:
        print(f"   ⚠️  Skipping row with invalid phone: {row.get('name', 'Unknown')}")
        continue
    
    # Add to monitored_contacts if not already there
    if phone not in bot_state["monitored_contacts"]:
        bot_state["monitored_contacts"].append(phone)
        new_contacts.append(phone)
    
    # Set contact time (use current time)
    bot_state["last_contact_time"][phone] = contact_time
    
    # Mark as not responded (since they want follow-up)
    bot_state["customer_responded"][phone] = False
    
    # Mark follow-up as sent (first follow-up already sent) - always set to True for these 40
    bot_state["followup_sent"][phone] = True
    
    # Initialize seen messages if not exists
    if phone not in bot_state["seen_message_ids"]:
        bot_state["seen_message_ids"][phone] = []
    if phone not in bot_state["seen_message_texts"]:
        bot_state["seen_message_texts"][phone] = []

# Update last_saved timestamp
bot_state["last_saved"] = datetime.now().isoformat()

# Write updated bot_state.json
with open(bot_state_file, 'w', encoding='utf-8') as f:
    json.dump(bot_state, f, indent=2, ensure_ascii=False)

print(f"   ✅ Added {len(new_contacts)} new contacts to bot_state.json")
print(f"   ✅ Total monitored contacts: {len(bot_state['monitored_contacts'])}")
print(f"   ✅ All 40 contacts marked as contacted with follow-up sent")
print(f"   ✅ Updated {bot_state_file}")

print(f"\n🎉 Done!")

