#!/usr/bin/env python3
"""
Script to merge clients_part_01.csv and clients_part_02.csv into a single file
"""

import csv
from pathlib import Path

# File paths
clients_dir = Path("clients_list")
part1_file = clients_dir / "clients_part_01.csv"
part2_file = clients_dir / "clients_part_02.csv"
output_file = Path("80 client list.csv")

print(f"📖 Reading {part1_file.name}...")
with open(part1_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    part1_rows = list(reader)
    fieldnames = list(reader.fieldnames)

print(f"   ✅ Read {len(part1_rows)} rows from part 1")

print(f"\n📖 Reading {part2_file.name}...")
with open(part2_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    part2_rows = list(reader)

print(f"   ✅ Read {len(part2_rows)} rows from part 2")

# Merge the rows
merged_rows = part1_rows + part2_rows
print(f"\n📝 Merging files...")
print(f"   Total rows to merge: {len(merged_rows)}")

# Write merged file
print(f"\n💾 Writing merged file: {output_file}")
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(merged_rows)

print(f"   ✅ Created {output_file} with {len(merged_rows)} rows")
print(f"\n🎉 Done!")

