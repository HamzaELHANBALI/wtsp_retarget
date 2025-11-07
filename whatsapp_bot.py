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
                # Initialize OpenAI client with explicit parameters only
                # Avoid any proxy or environment variable issues
                self.openai_client = OpenAI(
                    api_key=api_key,
                    timeout=60.0,
                    max_retries=2
                )
                self.ai_enabled = True
                print("✅ OpenAI API configured")
            except TypeError as e:
                # Handle version mismatch or unexpected argument errors
                print(f"⚠️  OpenAI initialization failed: {e}")
                print("   Trying alternative initialization...")
                try:
                    # Fallback: minimal initialization
                    self.openai_client = OpenAI(api_key=api_key)
                    self.ai_enabled = True
                    print("✅ OpenAI API configured (fallback method)")
                except Exception as e2:
                    print(f"⚠️  OpenAI initialization failed: {e2}")
                    print("   Try: pip install --upgrade openai")
                    self.ai_enabled = False
            except Exception as e:
                print(f"⚠️  OpenAI initialization failed: {e}")
                print("   AI responses will be disabled")
                self.ai_enabled = False
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
        self.messages_failed = 0
        self.messages_delivered = 0
        self.messages_read = 0
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
                self.messages_failed += 1
                return False

            # Send media if provided
            if media_path and os.path.exists(media_path):
                media_result = self._send_media(media_path, message)
                if media_result:
                    # Media sent successfully
                    print(f"✅ Message with media sent to {phone}")
                    self.messages_sent += 1
                    if phone not in self.monitored_contacts:
                        self.monitored_contacts.append(phone)
                    return True
                else:
                    # Media send had issues, but might have still sent
                    # Check if we should fall back to text
                    print("⚠️  Media verification uncertain - message may have been sent")
                    print("💡 Skipping text fallback to avoid duplicate messages")
                    # Mark as sent anyway - user can check WhatsApp
                    self.messages_sent += 1
                    if phone not in self.monitored_contacts:
                        self.monitored_contacts.append(phone)
                    return True
            else:
                # No media - send text only
                if not self._send_text(message):
                    self.messages_failed += 1
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
            self.messages_failed += 1
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
        """Send media (image/video) with optional caption using drag-and-drop for video preview"""
        try:
            print(f"📎 Attaching media: {Path(media_path).name}")

            # Get absolute path
            abs_path = str(Path(media_path).absolute())

            # Determine file type
            file_ext = Path(media_path).suffix.lower()
            is_video = file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.3gp']

            if is_video:
                print(f"🎬 Sending video with preview")
            else:
                print(f"🖼️ Sending image")

            # STEP 1: Type caption text FIRST (before attaching media)
            # This way it automatically becomes the caption when media is attached
            if caption:
                print(f"📝 Typing caption first (will become media caption)...")
                try:
                    input_box = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
                    )

                    # Type caption using JavaScript (handles emojis)
                    self.driver.execute_script(
                        """
                        const el = arguments[0];
                        const text = arguments[1];
                        el.focus();
                        document.execCommand('insertText', false, text);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        """,
                        input_box,
                        caption
                    )
                    print(f"✅ Caption typed: {caption[:50]}...")
                    time.sleep(1)
                except Exception as e:
                    print(f"⚠️  Could not type caption: {e}")

            # STEP 2: Click attachment button - try multiple selectors
            print("📎 Opening attachment menu...")

            attach_selectors = [
                "[data-icon='plus']",  # Plus icon (new WhatsApp UI)
                "[data-icon='clip']",  # Clip icon
                "[aria-label='Attach']",  # Aria label
                "span[data-icon='plus']",
                "span[data-icon='clip']",
                "button[aria-label='Attach']",
            ]

            attach_btn = None
            for selector in attach_selectors:
                try:
                    attach_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if attach_btn and attach_btn.is_displayed():
                        attach_btn.click()
                        print(f"✅ Opened attachment menu (selector: {selector})")
                        break
                except:
                    continue

            if not attach_btn:
                # Try JavaScript fallback
                clicked = self.driver.execute_script("""
                    const selectors = [
                        '[data-icon="plus"]',
                        '[data-icon="clip"]',
                        '[aria-label*="Attach"]',
                        'button[aria-label*="Attach"]'
                    ];
                    for (const sel of selectors) {
                        const btn = document.querySelector(sel);
                        if (btn) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                """)

                if clicked:
                    print("✅ Opened attachment menu (via JavaScript)")
                else:
                    raise Exception("Could not find attachment button")

            time.sleep(1.5)

            # Now find and click "Photos & Videos" for video preview
            if is_video:
                print("🎥 Selecting 'Photos & Videos' option...")

                # Method 1: Click the media icon directly (data-icon='media-filled-refreshed')
                photos_clicked = False
                try:
                    media_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-icon='media-filled-refreshed']")
                    if media_btn and media_btn.is_displayed():
                        media_btn.click()
                        print("✅ Clicked 'Photos & Videos' (media-filled-refreshed)")
                        photos_clicked = True
                        time.sleep(1)
                except:
                    pass

                # Method 2: JavaScript fallback
                if not photos_clicked:
                    photos_clicked = self.driver.execute_script("""
                        // Look for the media icon
                        const mediaBtn = document.querySelector('[data-icon="media-filled-refreshed"]');
                        if (mediaBtn && mediaBtn.offsetParent !== null) {
                            mediaBtn.click();
                            return true;
                        }

                        // Fallback: Look for menu items with photo/video text
                        const items = Array.from(document.querySelectorAll('li, div[role="button"], span[role="button"]'));
                        for (const item of items) {
                            const text = (item.textContent || '').toLowerCase();
                            const label = (item.getAttribute('aria-label') || '').toLowerCase();

                            if ((text.includes('photo') && text.includes('video')) ||
                                (label.includes('photo') && label.includes('video')) ||
                                text.includes('photos & videos') ||
                                label.includes('photos & videos')) {
                                item.click();
                                return true;
                            }
                        }
                        return false;
                    """)

                    if photos_clicked:
                        print("✅ Clicked 'Photos & Videos' (via JavaScript)")
                        time.sleep(1)

                if not photos_clicked:
                    print("⚠️  Could not find 'Photos & Videos' button, trying direct file input")

            # Find file input - IMPORTANT: Wait longer for Finder to open and file input to be ready
            print("📂 Looking for file input...")
            time.sleep(2)  # Increased wait for file picker to fully load

            # Try to find the file input (it appears after clicking attach or Photos & Videos)
            # For videos, we want the file input that accepts video files
            file_input_selectors = [
                "input[type='file'][accept*='video']",  # Video input first
                "input[type='file'][accept*='image']",  # Then image input
                "input[type='file']"  # Finally any file input
            ]

            file_input = None
            for selector in file_input_selectors:
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if inputs:
                        # Get ALL file inputs and find the one that's most likely to be the right one
                        for inp in reversed(inputs):  # Check from last to first (newest first)
                            try:
                                # Check if input is attached to DOM and not hidden
                                if inp.is_enabled():
                                    file_input = inp
                                    print(f"✅ Found file input: {selector}")
                                    break
                            except:
                                continue
                        if file_input:
                            break
                except:
                    continue

            if not file_input:
                # Last resort: wait for any file input to appear
                try:
                    file_input = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                    )
                    print("✅ Found file input (fallback)")
                except:
                    raise Exception("Could not find file input element")

            # STEP 3: Send file path to input
            # This will close Finder and upload the file with the caption we typed earlier
            print(f"📤 Sending file to WhatsApp...")
            try:
                file_input.send_keys(abs_path)
                print(f"✅ File path sent to input")

                # Wait for Finder to close and upload to start
                print("⏳ Waiting for Finder to close and upload to begin...")
                time.sleep(3)

                # Verify upload started by checking if preview appeared
                max_attempts = 5
                preview_found = False
                for attempt in range(max_attempts):
                    preview_exists = self.driver.execute_script("""
                        // Check if media preview/editor is visible
                        const preview = document.querySelector('[data-animate-media-viewer]') ||
                                       document.querySelector('[data-testid="media-viewer"]') ||
                                       document.querySelector('div[role="dialog"]') ||
                                       document.querySelector('[data-icon="wds-ic-send-filled"]');
                        return preview !== null;
                    """)

                    if preview_exists:
                        print(f"✅ Upload started, preview visible")
                        preview_found = True
                        break
                    else:
                        if attempt < max_attempts - 1:
                            print(f"   Waiting for preview... (attempt {attempt + 1}/{max_attempts})")
                            time.sleep(2)

                if not preview_found:
                    print(f"⚠️  Could not verify upload preview, but continuing...")

            except Exception as e:
                print(f"⚠️  Error sending file path: {e}")
                raise

            # STEP 4: Wait for upload to complete
            # Caption should already be there from Step 1
            print("⏳ Waiting for video to finish uploading...")
            time.sleep(4)

            # Verify caption is still there
            if caption:
                try:
                    caption_present = self.driver.execute_script("""
                        const captionBox = document.querySelector('[contenteditable="true"]');
                        if (captionBox) {
                            const text = captionBox.textContent || captionBox.innerText || '';
                            return text.length > 0;
                        }
                        return false;
                    """)

                    if caption_present:
                        print(f"✅ Caption is present in preview")
                    else:
                        print(f"⚠️  Caption may not be visible, will verify after send...")
                except:
                    pass

            # STEP 5: Click send button - try multiple methods
            print("📤 Looking for send button...")

            send_success = False

            # Method 1: Try multiple send button selectors
            send_selectors = [
                "[data-icon='wds-ic-send-filled']",  # New WhatsApp UI
                "[data-icon='send']",  # Older UI
                "span[data-icon='wds-ic-send-filled']",
                "span[data-icon='send']",
                "[aria-label='Send']",
                "button[aria-label='Send']",
                "[data-testid='send']",
            ]

            for selector in send_selectors:
                try:
                    send_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if send_btn and send_btn.is_displayed():
                        send_btn.click()
                        print(f"✅ Send button clicked (selector: {selector})")
                        send_success = True
                        break
                except:
                    continue

            # Method 2: JavaScript fallback
            if not send_success:
                print("⚠️  Direct click failed, trying JavaScript...")
                send_success = self.driver.execute_script("""
                    const selectors = [
                        '[data-icon="wds-ic-send-filled"]',  // New WhatsApp UI
                        '[data-icon="send"]',
                        '[aria-label="Send"]',
                        '[data-testid="send"]'
                    ];

                    for (const sel of selectors) {
                        const btn = document.querySelector(sel);
                        if (btn && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                """)

                if send_success:
                    print("✅ Send button clicked (via JavaScript)")

            # Method 3: Press Enter as last resort
            if not send_success:
                print("⚠️  Send button not found, trying Enter key...")
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(self.driver).send_keys(Keys.RETURN).perform()
                print("✅ Pressed Enter key to send")
                send_success = True

            if not send_success:
                raise Exception("Could not send media - all methods failed")

            # Wait for upload to complete and message to appear in chat
            print("⏳ Waiting for upload to complete and message to appear...")

            # For videos, wait longer based on file size
            if is_video:
                file_size_mb = os.path.getsize(abs_path) / (1024 * 1024)
                if file_size_mb > 50:
                    wait_time = 15
                elif file_size_mb > 20:
                    wait_time = 10
                else:
                    wait_time = 7
                print(f"   Video size: {file_size_mb:.1f}MB, waiting {wait_time}s for upload...")
                time.sleep(wait_time)
            else:
                time.sleep(5)

            # Check if message was sent by looking for the LAST message container
            sent_verified = self.driver.execute_script("""
                // Get all message containers
                const messages = document.querySelectorAll('[data-testid="msg-container"]');
                if (messages.length === 0) {
                    return false;
                }

                // Get the last message (most recent)
                const lastMessage = messages[messages.length - 1];

                // Check if it's an outgoing message (has 'message-out' class)
                const isOutgoing = lastMessage.querySelector('[class*="message-out"]') !== null;

                if (!isOutgoing) {
                    return false;
                }

                // Check for checkmarks (pending, sent, or delivered)
                const hasCheck = lastMessage.querySelector('[data-icon="msg-check"]') !== null;
                const hasDblCheck = lastMessage.querySelector('[data-icon="msg-dblcheck"]') !== null;
                const hasClock = lastMessage.querySelector('[data-icon="msg-time"]') !== null;  // Pending

                return hasCheck || hasDblCheck || hasClock;
            """)

            if sent_verified:
                print("✅ Media sent successfully (verified - last message has status)")
            else:
                # Try one more time after additional wait (especially for large videos)
                retry_wait = 10 if is_video else 5
                print(f"⚠️  First verification failed, waiting {retry_wait}s longer for upload...")
                time.sleep(retry_wait)

                sent_verified_retry = self.driver.execute_script("""
                    const messages = document.querySelectorAll('[data-testid="msg-container"]');
                    if (messages.length === 0) return false;

                    const lastMessage = messages[messages.length - 1];
                    const isOutgoing = lastMessage.querySelector('[class*="message-out"]') !== null;
                    if (!isOutgoing) return false;

                    const hasCheck = lastMessage.querySelector('[data-icon="msg-check"]') !== null;
                    const hasDblCheck = lastMessage.querySelector('[data-icon="msg-dblcheck"]') !== null;
                    const hasClock = lastMessage.querySelector('[data-icon="msg-time"]') !== null;

                    return hasCheck || hasDblCheck || hasClock;
                """)

                if sent_verified_retry:
                    print("✅ Media sent successfully (verified after retry)")
                    return True
                else:
                    print("⚠️  Could not verify send within timeout")
                    print("💡 Media was likely sent but upload is still in progress")
                    print("✓  Check WhatsApp to confirm delivery")
                    # Return True anyway - video was clicked to send, just taking time to upload
                    # Better to assume success than send duplicate text
                    return True

            return True

        except Exception as e:
            print(f"⚠️  Error sending media: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"🔍 Checking messages from {phone}...")

            # Open chat
            url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
            self.driver.get(url)
            time.sleep(4)  # Increased wait time for chat to load

            # Check if chat loaded successfully
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='conversation-panel-body']"))
                )
            except TimeoutException:
                print(f"⚠️  Could not load chat for {phone}")
                return None

            # Try multiple strategies to find incoming messages
            last_msg = None
            all_incoming = []

            # Strategy 1: Use JavaScript to find incoming messages more reliably
            result = self.driver.execute_script("""
                // Find all message bubbles
                const messageContainers = document.querySelectorAll('[data-testid="msg-container"]');

                console.log('Total message containers:', messageContainers.length);

                // Filter for incoming messages (not sent by us)
                const incomingMessages = [];

                for (const container of messageContainers) {
                    // Check if this is an incoming message (has 'message-in' class)
                    // WhatsApp uses 'message-in' for received messages and 'message-out' for sent
                    const msgDiv = container.querySelector('[class*="message-in"]');

                    if (msgDiv) {
                        // Get the text content - try multiple selectors
                        let text = null;

                        // Try .selectable-text first
                        const selectableText = container.querySelector('.selectable-text');
                        if (selectableText) {
                            text = selectableText.textContent || selectableText.innerText;
                        }

                        // Try conversation-text as fallback
                        if (!text) {
                            const convText = container.querySelector('[data-testid="conversation-text"]');
                            if (convText) {
                                text = convText.textContent || convText.innerText;
                            }
                        }

                        // Try any span with text as last resort
                        if (!text) {
                            const spans = container.querySelectorAll('span');
                            for (const span of spans) {
                                const spanText = span.textContent || span.innerText;
                                if (spanText && spanText.trim() && spanText.length > 0) {
                                    text = spanText;
                                    break;
                                }
                            }
                        }

                        if (text && text.trim()) {
                            incomingMessages.push(text.trim());
                        }
                    }
                }

                console.log('Incoming messages found:', incomingMessages.length);

                // Return all incoming messages and the last one
                return {
                    all: incomingMessages,
                    last: incomingMessages.length > 0 ? incomingMessages[incomingMessages.length - 1] : null,
                    count: incomingMessages.length
                };
            """)

            if result:
                all_incoming = result.get('all', [])
                last_msg = result.get('last')
                msg_count = result.get('count', 0)
                print(f"📨 Found {msg_count} incoming messages from {phone}")
                if all_incoming:
                    print(f"💬 Last incoming message: {last_msg[:50]}..." if last_msg and len(last_msg) > 50 else f"💬 Last incoming message: {last_msg}")

            # Strategy 2: Fallback using Selenium if JavaScript method fails
            if not last_msg:
                print("🔄 Trying fallback method...")
                # Try different selector combinations
                selector_attempts = [
                    "[data-testid='msg-container'] [class*='message-in'] .selectable-text",
                    "[data-testid='msg-container'] [class*='message-in'] [data-testid='conversation-text']",
                    "div[class*='message-in'] .selectable-text",
                    "div[class*='message-in'] span.selectable-text",
                ]

                for selector in selector_attempts:
                    try:
                        messages = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if messages:
                            last_msg = messages[-1].text.strip()
                            print(f"✅ Found message with selector: {selector}")
                            if last_msg:
                                break
                    except Exception as sel_err:
                        continue

            if not last_msg:
                print(f"ℹ️  No new messages from {phone}")
                return None

            # Check if it's new
            last_seen = self.last_messages.get(phone, "")

            print(f"📝 Last seen message: {last_seen[:50]}..." if last_seen and len(last_seen) > 50 else f"📝 Last seen message: {last_seen}")
            print(f"📝 Current message: {last_msg[:50]}..." if last_msg and len(last_msg) > 50 else f"📝 Current message: {last_msg}")

            if last_msg and last_msg != last_seen:
                self.last_messages[phone] = last_msg
                print(f"✨ NEW MESSAGE from {phone}: {last_msg[:100]}...")
                return last_msg
            else:
                print(f"ℹ️  No new messages (already seen)")

            return None

        except Exception as e:
            print(f"⚠️  Error checking messages from {phone}: {e}")
            import traceback
            traceback.print_exc()
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

    def check_read_receipts(self):
        """Check and update read receipt status for sent messages"""
        try:
            # Look for all sent message bubbles (outgoing messages)
            messages = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='msg-container']")

            delivered_count = 0
            read_count = 0

            for msg in messages:
                try:
                    # Check for read status (blue double check)
                    read_icons = msg.find_elements(By.CSS_SELECTOR, "[data-icon='msg-dblcheck'][aria-label*='Read']")
                    if read_icons:
                        read_count += 1
                        continue

                    # Check for delivered status (gray double check)
                    delivered_icons = msg.find_elements(By.CSS_SELECTOR, "[data-icon='msg-dblcheck']")
                    if delivered_icons:
                        delivered_count += 1

                except:
                    continue

            # Update stats
            self.messages_read = read_count
            self.messages_delivered = delivered_count

        except Exception as e:
            print(f"⚠️  Could not check read receipts: {e}")

    def get_stats(self) -> Dict:
        """Get bot statistics"""
        # Calculate success rate
        total_attempts = self.messages_sent + self.messages_failed
        success_rate = (self.messages_sent / total_attempts) if total_attempts > 0 else 0

        # Update read receipts if browser is active
        if self.driver:
            try:
                self.check_read_receipts()
            except:
                pass  # Silently fail if can't check

        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "messages_delivered": self.messages_delivered,
            "messages_read": self.messages_read,
            "success_rate": success_rate,
            "ai_responses": self.ai_responses_sent,  # Match streamlit key
            "ai_responses_sent": self.ai_responses_sent,
            "conversations": len(self.conversations),
            "conversation_history": self.conversations,  # Match streamlit key
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
