"""
Debug helper to inspect WhatsApp Web UI and find correct selectors
Run this when WhatsApp Web is open with a chat
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
import time

def inspect_whatsapp():
    """Open WhatsApp Web and print all available selectors"""

    options = webdriver.ChromeOptions()
    profile_path = Path.cwd() / "whatsapp_profile"
    options.add_argument(f"--user-data-dir={profile_path}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://web.whatsapp.com")
    time.sleep(5)

    print("\n" + "="*60)
    print("WHATSAPP WEB INSPECTOR")
    print("="*60)

    print("\nPlease open a chat and click the attachment button manually")
    print("Then press Enter here...")
    input()

    print("\n📋 Looking for attachment-related elements...")

    # Check for attachment buttons
    attachment_icons = driver.execute_script("""
        const results = [];

        // Look for attachment buttons
        const attachSelectors = [
            '[data-icon]',
            '[aria-label*="ttach"]',
            'button',
            'span[role="button"]'
        ];

        attachSelectors.forEach(sel => {
            const elements = document.querySelectorAll(sel);
            elements.forEach(el => {
                if (el.offsetParent !== null) {  // visible
                    results.push({
                        selector: sel,
                        dataIcon: el.getAttribute('data-icon'),
                        ariaLabel: el.getAttribute('aria-label'),
                        className: el.className,
                        text: el.textContent.substring(0, 50)
                    });
                }
            });
        });

        return results;
    """)

    print("\n🔍 Found attachment-related elements:")
    for i, elem in enumerate(attachment_icons[:20], 1):  # Show first 20
        print(f"\n{i}. Selector: {elem['selector']}")
        if elem['dataIcon']:
            print(f"   data-icon: {elem['dataIcon']}")
        if elem['ariaLabel']:
            print(f"   aria-label: {elem['ariaLabel']}")
        if elem['className']:
            print(f"   class: {elem['className'][:100]}")

    print("\n\nNow, please attach a file manually and wait for upload")
    print("Then press Enter here...")
    input()

    # Check for send button
    send_buttons = driver.execute_script("""
        const results = [];

        const sendSelectors = [
            '[data-icon]',
            '[aria-label*="end"]',
            'button',
            'span[role="button"]'
        ];

        sendSelectors.forEach(sel => {
            const elements = document.querySelectorAll(sel);
            elements.forEach(el => {
                if (el.offsetParent !== null) {
                    results.push({
                        selector: sel,
                        dataIcon: el.getAttribute('data-icon'),
                        ariaLabel: el.getAttribute('aria-label'),
                        className: el.className
                    });
                }
            });
        });

        return results;
    """)

    print("\n📤 Found send-related elements:")
    for i, elem in enumerate(send_buttons[:20], 1):
        print(f"\n{i}. Selector: {elem['selector']}")
        if elem['dataIcon']:
            print(f"   data-icon: {elem['dataIcon']}")
        if elem['ariaLabel']:
            print(f"   aria-label: {elem['ariaLabel']}")
        if elem['className']:
            print(f"   class: {elem['className'][:100]}")

    print("\n" + "="*60)
    print("✅ Inspection complete!")
    print("="*60)

    print("\nPress Enter to close...")
    input()

    driver.quit()

if __name__ == "__main__":
    inspect_whatsapp()
