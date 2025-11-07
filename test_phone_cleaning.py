"""
Test script for phone number cleaning functions
Tests various Saudi phone number formats including Arabic numerals
"""

from clean_order_csv import clean_phone_number, convert_arabic_numerals, clean_name

print("=" * 70)
print("Phone Number Cleaning Tests")
print("=" * 70)
print()

# Test cases for phone numbers
test_phones = [
    # Arabic numerals
    ("٠٥٠٧٨٨٩٣٨٧", "+966507889387", "Arabic numerals with leading zero"),
    ("٥٠١٢٣٤٥٦٧", "+966501234567", "Arabic numerals without leading zero"),

    # Standard formats
    ("+966501234567", "+966501234567", "Already formatted correctly"),
    ("966501234567", "+966501234567", "Country code without +"),
    ("0501234567", "+966501234567", "Saudi local format with 0"),
    ("501234567", "+966501234567", "Saudi local format without 0"),

    # With spaces and special characters
    ("050 099 0167", "+966500990167", "Spaces in number"),
    ("050-099-0167", "+966500990167", "Dashes in number"),
    ("(050) 099 0167", "+966500990167", "Parentheses and spaces"),
    ("+966 50 123 4567", "+966501234567", "Spaces after country code"),

    # Mixed Arabic and English
    ("٠٥٠١٢٣٤٥٦٧", "+966501234567", "Mixed Arabic numerals"),

    # Invalid formats (should return None)
    ("", None, "Empty string"),
    ("123", None, "Too short"),
    ("abcd", None, "Non-numeric"),
    ("12345", None, "Incomplete number"),
]

print("Testing phone number cleaning:")
print("-" * 70)

passed = 0
failed = 0

for phone_input, expected, description in test_phones:
    result = clean_phone_number(phone_input, "+966")
    status = "✅ PASS" if result == expected else "❌ FAIL"

    if result == expected:
        passed += 1
    else:
        failed += 1

    print(f"{status} | {description}")
    print(f"   Input:    '{phone_input}'")
    print(f"   Expected: {expected}")
    print(f"   Got:      {result}")
    print()

print("=" * 70)
print(f"Results: {passed} passed, {failed} failed out of {len(test_phones)} tests")
print("=" * 70)
print()

# Test Arabic numeral conversion
print("Testing Arabic numeral conversion:")
print("-" * 70)

arabic_tests = [
    ("٠١٢٣٤٥٦٧٨٩", "0123456789", "All Arabic digits"),
    ("٠٥٠١٢٣٤٥٦٧", "0501234567", "Saudi phone with Arabic numerals"),
    ("Test ١٢٣", "Test 123", "Mixed text and Arabic numerals"),
]

for arabic_input, expected, description in arabic_tests:
    result = convert_arabic_numerals(arabic_input)
    status = "✅ PASS" if result == expected else "❌ FAIL"

    print(f"{status} | {description}")
    print(f"   Input:    '{arabic_input}'")
    print(f"   Expected: '{expected}'")
    print(f"   Got:      '{result}'")
    print()

# Test name cleaning
print("=" * 70)
print("Testing name cleaning:")
print("-" * 70)

name_tests = [
    ("Ahmed", "Ahmed", "Simple English name"),
    ("ناصر الخالدي", "ناصر الخالدي", "Arabic name"),
    ("  Fatima  ", "Fatima", "Extra spaces"),
    ("Mohammed   Ali", "Mohammed Ali", "Multiple spaces"),
    ("", "Customer", "Empty name"),
    (None, "Customer", "None value"),
]

for name_input, expected, description in name_tests:
    result = clean_name(name_input)
    status = "✅ PASS" if result == expected else "❌ FAIL"

    print(f"{status} | {description}")
    print(f"   Input:    '{name_input}'")
    print(f"   Expected: '{expected}'")
    print(f"   Got:      '{result}'")
    print()

print("=" * 70)
print("All tests complete!")
print("=" * 70)
