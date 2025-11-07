"""
WhatsApp Bulk Messaging Bot with AI Auto-Responses
Modern, simplified implementation with robust error handling
"""

import os
import time
import random
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from openai import OpenAI
from dotenv import load_dotenv


class WhatsAppBot:
    """
    WhatsApp Web automation bot with AI-powered responses

    Features:
    - Send bulk messages (text + media)
    - Monitor incoming messages
    - AI-powered auto-responses using OpenAI
    - Persistent session (no repeated QR scans)
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        headless: bool = False
    ):
        """
        Initialize WhatsApp Bot

        Args:
            openai_api_key: OpenAI API key (or set in .env file)
            system_prompt: Custom AI system prompt
            headless: Run browser in headless mode (not recommended for WhatsApp)
        """
        # Load environment variables
        load_dotenv()

        # Setup OpenAI
        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.ai_enabled = False
        self.openai_client = None

        if api_key:
            try:
                self.openai_client = OpenAI(api_key=api_key)
                self.ai_enabled = True
                print("✅ OpenAI API configured")
            except Exception as e:
                print(f"⚠️  OpenAI initialization failed: {e}")
        else:
            print("⚠️  OpenAI API key not found. AI responses disabled.")
            print("   Add OPENAI_API_KEY to .env file to enable AI responses")

        # AI configuration
        self.system_prompt = system_prompt or """You are a helpful customer service representative.
Respond professionally in the customer's language (Arabic or English).
Keep responses concise and helpful."""

        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

        # Conversation tracking
        self.conversations: Dict[str, List[Dict]] = {}
        self.last_messages: Dict[str, str] = {}
        self.monitored_contacts: List[str] = []

        # Statistics
        self.messages_sent = 0
        self.ai_responses_sent = 0

        # Setup browser
        self.driver = None
        self.wait = None
        self._setup_browser(headless)

    def _setup_browser(self, headless: bool = False):
        """Setup Chrome browser with WhatsApp Web"""
        print("🌐 Setting up browser...")

        # Chrome options
        options = webdriver.ChromeOptions()

        # Persistent profile for session management
        profile_path = Path.cwd() / "whatsapp_profile"
        profile_path.mkdir(exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_path}")

        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Additional options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if headless:
            options.add_argument("--headless=new")
            print("ℹ️  Running in headless mode")

        # User agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            # Auto-install ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)

            # Stealth modifications
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": self.driver.execute_script("return navigator.userAgent").replace('Headless', '')
            })
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.wait = WebDriverWait(self.driver, 20)
            print("✅ Browser setup complete")

            # Login to WhatsApp Web
            self._login_whatsapp()

        except Exception as e:
            print(f"❌ Browser setup failed: {e}")
            raise

    def _login_whatsapp(self):
        """Login to WhatsApp Web"""
        print("🔐 Connecting to WhatsApp Web...")

        self.driver.get("https://web.whatsapp.com")
        time.sleep(3)

        # Check if already logged in
        try:
            # Look for chat list (logged in indicator)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Chat list']"))
            )
            print("✅ Already logged in (session restored)")
            return
        except TimeoutException:
            pass

        # Not logged in - wait for QR scan
        print("\n" + "="*60)
        print("📱 QR CODE SCAN REQUIRED")
        print("="*60)
        print("\n1. Open WhatsApp on your phone")
        print("2. Go to: Settings → Linked Devices")
        print("3. Tap 'Link a Device'")
        print("4. Scan the QR code in the browser")
        print("\n" + "="*60)
        print("⏳ Waiting for QR scan...")
        print("="*60 + "\n")

        try:
            # Wait for successful login (chat list appears)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Chat list']"))
            )
            print("✅ Login successful! Session saved.")
            time.sleep(2)
        except TimeoutException:
            print("❌ Login timeout. Please try again.")
            raise

    def _format_phone(self, phone: str) -> str:
        """Format phone number for WhatsApp"""
        # Remove spaces, dashes, parentheses
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')

        # Add + if missing
        if not phone.startswith('+'):
            # Assume Saudi number if no country code
            if phone.startswith('966'):
                phone = '+' + phone
            elif phone.startswith('0'):
                phone = '+966' + phone[1:]
            else:
                phone = '+966' + phone

        return phone

    def send_message(
        self,
        phone: str,
        message: str,
        media_path: Optional[str] = None
    ) -> bool:
        """
        Send message to a contact

        Args:
            phone: Phone number (e.g., "+966501234567")
            message: Message text (or caption if media provided)
            media_path: Optional path to image/video file

        Returns:
            True if sent successfully
        """
        try:
            phone = self._format_phone(phone)
            print(f"\n📤 Sending to {phone}...")

            # Open chat
            url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
            self.driver.get(url)

            # Wait for chat to load
            time.sleep(random.uniform(3, 5))

            # Check if number is valid (chat loaded)
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
                )
            except TimeoutException:
                print(f"❌ Invalid number or chat not loaded: {phone}")
                return False

            # Send media if provided
            if media_path and os.path.exists(media_path):
                if not self._send_media(media_path, message):
                    print("⚠️  Media send failed, falling back to text only")
                    media_path = None

            # Send text (if no media or media failed)
            if not media_path:
                if not self._send_text(message):
                    return False

            # Verify sent
            time.sleep(2)
            print(f"✅ Message sent to {phone}")

            self.messages_sent += 1

            # Add to monitoring list
            if phone not in self.monitored_contacts:
                self.monitored_contacts.append(phone)

            return True

        except Exception as e:
            print(f"❌ Error sending to {phone}: {e}")
            return False

    def _send_text(self, message: str) -> bool:
        """Send text message"""
        try:
            # Find message input box
            input_box = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
            )

            # Type message using JavaScript (handles emojis properly)
            self.driver.execute_script(
                """
                const el = arguments[0];
                const text = arguments[1];
                el.focus();
                document.execCommand('insertText', false, text);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                """,
                input_box,
                message
            )

            time.sleep(1)

            # Send
            input_box.send_keys(Keys.RETURN)
            time.sleep(1)

            return True

        except Exception as e:
            print(f"⚠️  Error sending text: {e}")
            return False

    def _send_media(self, media_path: str, caption: str = "") -> bool:
        """Send media (image/video) with optional caption"""
        try:
            print(f"📎 Attaching media: {Path(media_path).name}")

            # Find attachment button
            attach_btn = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-icon='attach-menu-plus'], [data-icon='clip']"))
            )
            attach_btn.click()
            time.sleep(1)

            # Find file input
            file_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )

            # Upload file
            abs_path = str(Path(media_path).absolute())
            file_input.send_keys(abs_path)

            print("⏳ Uploading media...")
            time.sleep(3)

            # Add caption if provided
            if caption:
                try:
                    caption_box = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
                    )

                    self.driver.execute_script(
                        """
                        const el = arguments[0];
                        const text = arguments[1];
                        el.focus();
                        document.execCommand('insertText', false, text);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        """,
                        caption_box,
                        caption
                    )

                    time.sleep(1)
                    print(f"📝 Caption added")

                except Exception as e:
                    print(f"⚠️  Could not add caption: {e}")

            # Wait for upload to complete and send button to be enabled
            time.sleep(2)

            # Click send button
            send_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-icon='send']"))
            )
            send_btn.click()

            print("✅ Media sent")
            time.sleep(3)

            return True

        except Exception as e:
            print(f"⚠️  Error sending media: {e}")
            return False

    def get_new_messages(self, phone: str) -> Optional[str]:
        """
        Check for new messages from a contact

        Args:
            phone: Phone number to check

        Returns:
            New message text if found, None otherwise
        """
        try:
            phone = self._format_phone(phone)

            # Open chat
            url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
            self.driver.get(url)
            time.sleep(2)

            # Get all messages
            messages = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-testid='msg-container'] [class*='message-in'] .selectable-text"
            )

            if not messages:
                return None

            # Get last incoming message
            last_msg = messages[-1].text.strip()

            # Check if it's new
            last_seen = self.last_messages.get(phone, "")

            if last_msg and last_msg != last_seen:
                self.last_messages[phone] = last_msg
                return last_msg

            return None

        except Exception as e:
            print(f"⚠️  Error checking messages from {phone}: {e}")
            return None

    def generate_ai_response(self, message: str, phone: str) -> str:
        """
        Generate AI response using OpenAI

        Args:
            message: Customer message
            phone: Customer phone number

        Returns:
            AI-generated response
        """
        if not self.ai_enabled:
            return "Thank you for your message. We'll get back to you soon."

        try:
            # Get conversation history
            history = self.conversations.get(phone, [])

            # Build messages for API
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Add history (last 10 messages)
            messages.extend(history[-10:])

            # Add current message
            messages.append({"role": "user", "content": message})

            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )

            ai_response = response.choices[0].message.content.strip()

            # Update conversation history
            if phone not in self.conversations:
                self.conversations[phone] = []

            self.conversations[phone].append({"role": "user", "content": message})
            self.conversations[phone].append({"role": "assistant", "content": ai_response})

            # Keep only last 20 messages
            if len(self.conversations[phone]) > 20:
                self.conversations[phone] = self.conversations[phone][-20:]

            return ai_response

        except Exception as e:
            print(f"⚠️  AI response error: {e}")
            return "Thank you for your message. We'll get back to you soon."

    def monitor_and_respond(self, check_interval: int = 10, duration: Optional[int] = None):
        """
        Monitor contacts for new messages and respond automatically

        Args:
            check_interval: Seconds between checks
            duration: Optional duration in seconds (None = run indefinitely)
        """
        if not self.ai_enabled:
            print("⚠️  AI not enabled. Cannot auto-respond.")
            return

        if not self.monitored_contacts:
            print("⚠️  No contacts to monitor. Send messages first.")
            return

        print(f"\n🤖 AI Monitoring Started")
        print(f"   Monitoring {len(self.monitored_contacts)} contact(s)")
        print(f"   Check interval: {check_interval}s")
        if duration:
            print(f"   Duration: {duration}s")
        print("   Press Ctrl+C to stop\n")

        start_time = time.time()
        cycle = 0

        try:
            while True:
                cycle += 1
                print(f"\n🔄 Check #{cycle} - {datetime.now().strftime('%H:%M:%S')}")

                for phone in self.monitored_contacts:
                    print(f"   Checking {phone}...", end=" ")

                    new_msg = self.get_new_messages(phone)

                    if new_msg:
                        print(f"📨 New message!")
                        print(f"   Customer: {new_msg[:50]}...")

                        # Generate AI response
                        print("   🤖 Generating response...")
                        ai_response = self.generate_ai_response(new_msg, phone)
                        print(f"   AI: {ai_response[:50]}...")

                        # Send response
                        if self.send_message(phone, ai_response):
                            self.ai_responses_sent += 1
                            print("   ✅ Response sent")
                        else:
                            print("   ❌ Response failed")
                    else:
                        print("No new messages")

                    time.sleep(1)

                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    print(f"\n⏱️  Duration reached ({duration}s)")
                    break

                # Wait before next cycle
                print(f"   ⏳ Next check in {check_interval}s...")
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")

    def get_stats(self) -> Dict:
        """Get bot statistics"""
        return {
            "messages_sent": self.messages_sent,
            "ai_responses_sent": self.ai_responses_sent,
            "conversations": len(self.conversations),
            "monitored_contacts": len(self.monitored_contacts)
        }

    def close(self):
        """Close browser and cleanup"""
        if self.driver:
            print("\n📊 Final Statistics:")
            stats = self.get_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")

            self.driver.quit()
            print("✅ Browser closed")


if __name__ == "__main__":
    # Quick test
    bot = WhatsAppBot()
    print("\n✅ WhatsApp Bot initialized successfully!")
    print("   Import this class in your script to use it.")
    bot.close()
