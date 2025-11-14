#!/usr/bin/env python3
"""
Categorize clients from KECHDISCOUNTS orders CSV file
- Extract 200 women (filter by Arabic female names)
- Extract customers by product (Wooden Electric Cigarette Holder)
"""

import csv
import os
from pathlib import Path

# Arabic female name patterns and common names
FEMALE_NAME_INDICATORS = [
    # Names ending with ta marbuta (ة)
    'ة',
    # Common Arabic female names
    'فاطمة', 'مريم', 'عائشة', 'خديجة', 'آمنة', 'زينب', 'رقية', 'أم كلثوم',
    'ريم', 'نور', 'سارة', 'لينا', 'نورة', 'سمر', 'شيماء', 'هند', 'خلود',
    'فاتن', 'فيروز', 'ليلى', 'غادة', 'سعاد', 'سلمى', 'علا', 'لانا', 'ميس',
    'رغد', 'رهف', 'ريناد', 'رانيا', 'روان', 'ريان', 'رؤى', 'راما', 'رنا',
    'دانة', 'داليا', 'دينا', 'ديما', 'دعاء', 'دنيا',
    'جمانة', 'جنى', 'جلنار',
    'حلا', 'حنان', 'حبيبة', 'حياة',
    'سجى', 'سندس', 'سندريلا', 'سمية',
    'شهد', 'شذى', 'شروق', 'شيرين',
    'صباح', 'صبا', 'صفاء', 'صوفي',
    'ضحى', 'ضياء',
    'عذراء', 'عنود', 'عروب',
    'غادة', 'غزل', 'غيداء',
    'فريدة', 'فادية', 'فدوى',
    'كارمن', 'كادي', 'كلثوم',
    'ليلى', 'لينا', 'لمى', 'لارا', 'لوجين',
    'مريم', 'مها', 'ميساء', 'ملاك', 'ملك', 'منال', 'مودة', 'موزة',
    'نادرة', 'ناهد', 'نهلة', 'نور', 'نورا', 'نورة', 'نورين', 'نوف', 'نادية',
    'هالة', 'هبة', 'هدى', 'هند', 'هيا', 'هيفاء',
    'ولاء', 'وجدان', 'وفاء',
    'يسرى', 'ياسمين', 'يامنة',
    # Names starting with "أم" (Umm - mother of)
    'أم ',
    'ام ',
]

# Products to filter
TARGET_PRODUCT = "Wooden Electric Cigarette Holder"

def is_female_name(name):
    """Check if a name is likely a female Arabic name"""
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    if not name:
        return False
    
    name_lower = name.lower()
    
    # Exclude clearly male names (even if they have female indicators)
    clearly_male_indicators = ['ناصر', 'محمد', 'أحمد', 'خالد', 'عبدالله', 'عبد الله', 'عبدالعزيز', 
                               'عبد الرحمن', 'سعد', 'فيصل', 'علي', 'عمر', 'عمار', 'عماد', 'عبدالرحمن']
    # Check if name starts with or contains clearly male names
    for male_ind in clearly_male_indicators:
        # If the name starts with a clearly male name (not "ام" prefix), exclude it
        if name_lower.startswith(male_ind.lower()) and not (name_lower.startswith('ام ') or name_lower.startswith('أم ')):
            return False
        # If name contains male name and it's the main part (not in "ام X" format), exclude
        if male_ind.lower() in name_lower and not (name_lower.startswith('ام ') or name_lower.startswith('أم ')):
            # Allow if it's clearly a compound female name like "ريناد ناصر" (first name is female)
            if any(female in name_lower.split()[0] if ' ' in name else False for female in ['ريم', 'ريناد', 'رغد', 'رهف', 'نور', 'مريم']):
                continue
            # But if male name appears early in the name, it's likely male
            name_parts = name_lower.split()
            if name_parts and male_ind.lower() in name_parts[0]:
                return False
    
    # Check for names starting with "أم" or "ام" (Umm) - these are almost always female
    if name.startswith('أم ') or name.startswith('ام '):
        return True
    
    # Check if name ends with ta marbuta (ة) - strong female indicator
    if name.endswith('ة'):
        return True
    
    # Check against common female names list
    for female_name in FEMALE_NAME_INDICATORS:
        if female_name in name_lower or name_lower.startswith(female_name.lower()):
            return True
    
    # Additional patterns: check if name contains common female name parts
    female_keywords = ['ريم', 'سارة', 'لينا', 'مريم', 'فاطمة', 'عائشة', 'زينب', 'خديجة', 'رقية', 
                       'سمر', 'شيماء', 'هند', 'خلود', 'ليلى', 'سلمى', 'نورا', 'نورة', 'رغد', 'رهف',
                       'ريناد', 'رانيا', 'روان', 'رؤى', 'رama', 'رنا', 'احلام', 'امينة', 'منيرة',
                       'صباح', 'حنان', 'هدى', 'هبة', 'هالة']
    for keyword in female_keywords:
        if keyword in name_lower:
            return True
    
    return False

def clean_phone(phone):
    """Clean and normalize phone number"""
    if not phone:
        return ""
    # Remove spaces, dashes, and non-digit characters except +
    phone = str(phone).strip()
    # Keep the phone as is for now, cleaning will be done by the main app
    return phone

def categorize_clients():
    """Main function to categorize clients"""
    input_file = "KECHDISCOUNTS - Youcan-Orders.csv"
    output_dir = Path("clients_list_categorized")
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    print(f"✅ Created directory: {output_dir}")
    
    # Read input CSV
    print(f"📖 Reading input file: {input_file}")
    women_clients = []
    product_clients = []
    seen_phones_women = set()  # To avoid duplicates
    seen_phones_product = set()  # To avoid duplicates
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_rows = 0
        
        for row in reader:
            total_rows += 1
            name = row.get('name', '').strip()
            phone = clean_phone(row.get('phone', ''))
            address = row.get('address', '').strip()
            product = row.get('Product', '').strip()
            order_date = row.get('OrderDate', '').strip()
            
            # Skip if no phone number
            if not phone:
                continue
            
            # Filter ALL women (no limit)
            if is_female_name(name) and phone not in seen_phones_women:
                women_clients.append({
                    'name': name,
                    'phone': phone,
                    'address': address,
                    'order_date': order_date,
                    'product': product
                })
                seen_phones_women.add(phone)
            
            # Filter by product
            if TARGET_PRODUCT.lower() in product.lower() and phone not in seen_phones_product:
                product_clients.append({
                    'name': name,
                    'phone': phone,
                    'address': address,
                    'order_date': order_date,
                    'product': product
                })
                seen_phones_product.add(phone)
    
    print(f"📊 Total rows processed: {total_rows}")
    print(f"👩 Women clients found: {len(women_clients)} (unique by phone)")
    print(f"🛍️  Product '{TARGET_PRODUCT}' clients found: {len(product_clients)}")
    
    # Split women clients into chunks of 50
    chunk_size = 50
    total_chunks = (len(women_clients) + chunk_size - 1) // chunk_size  # Ceiling division
    
    print(f"\n📦 Splitting {len(women_clients)} women into {total_chunks} files of {chunk_size} each...")
    
    for i in range(total_chunks):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, len(women_clients))
        chunk = women_clients[start_idx:end_idx]
        
        chunk_file = output_dir / f"women_clients_part_{i+1:02d}_of_{total_chunks:02d}.csv"
        with open(chunk_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['name', 'phone', 'address', 'order_date', 'product']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chunk)
        print(f"✅ Created: {chunk_file} ({len(chunk)} clients, rows {start_idx+1}-{end_idx})")
    
    # Also create a full list file for reference
    full_women_file = output_dir / "women_clients_full_list.csv"
    with open(full_women_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['name', 'phone', 'address', 'order_date', 'product']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(women_clients)
    print(f"✅ Created: {full_women_file} ({len(women_clients)} clients - FULL LIST)")
    
    # Write product clients CSV
    product_file = output_dir / "wooden_cigarette_holder_clients.csv"
    with open(product_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['name', 'phone', 'address', 'order_date', 'product']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(product_clients)
    print(f"✅ Created: {product_file} ({len(product_clients)} clients)")
    
    # Print sample names for verification
    print(f"\n📋 Sample women names (first 10):")
    for i, client in enumerate(women_clients[:10], 1):
        print(f"  {i}. {client['name']}")
    
    print(f"\n📋 Sample product clients names (first 10):")
    for i, client in enumerate(product_clients[:10], 1):
        print(f"  {i}. {client['name']} - {client['product']}")
    
    print(f"\n✅ Categorization complete!")
    return len(women_clients), len(product_clients)

if __name__ == "__main__":
    categorize_clients()

