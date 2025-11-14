#!/usr/bin/env python3
"""
Count total number of women in the KECHDISCOUNTS orders CSV file
"""

import csv
from categorize_clients import is_female_name, clean_phone

def count_women_in_file():
    """Count all women in the CSV file"""
    input_file = "KECHDISCOUNTS - Youcan-Orders.csv"
    
    print(f"📖 Reading input file: {input_file}")
    women_count = 0
    total_rows = 0
    women_with_phone = 0
    unique_women_phones = set()
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            total_rows += 1
            name = row.get('name', '').strip()
            phone = clean_phone(row.get('phone', ''))
            
            if is_female_name(name):
                women_count += 1
                if phone:
                    women_with_phone += 1
                    unique_women_phones.add(phone)
    
    print(f"\n📊 Results:")
    print(f"   Total rows processed: {total_rows}")
    print(f"   Women found (by name): {women_count}")
    print(f"   Women with phone numbers: {women_with_phone}")
    print(f"   Unique women (by phone): {len(unique_women_phones)}")
    print(f"\n📈 Percentage:")
    print(f"   Women / Total: {women_count}/{total_rows} = {(women_count/total_rows)*100:.2f}%")
    print(f"   Unique women / Total: {len(unique_women_phones)}/{total_rows} = {(len(unique_women_phones)/total_rows)*100:.2f}%")
    
    return women_count, len(unique_women_phones)

if __name__ == "__main__":
    count_women_in_file()

