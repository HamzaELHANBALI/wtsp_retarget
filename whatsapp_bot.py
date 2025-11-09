"""
WhatsApp Bulk Messaging Bot with AI Auto-Responses
Modern, simplified implementation with robust error handling
"""

import os
import time
import random
import csv
import re
import threading
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
from clean_order_csv import convert_arabic_numerals


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
        headless: bool = False,
        contacts_df = None
    ):
        """
        Initialize WhatsApp Bot

        Args:
            openai_api_key: OpenAI API key (or set in .env file)
            system_prompt: Custom AI system prompt
            headless: Run browser in headless mode (not recommended for WhatsApp)
            contacts_df: DataFrame with customer data (name, phone, address/city)
        """
        # Load environment variables
        load_dotenv()

        # Store contacts dataframe for customer lookup
        self.contacts_df = contacts_df

        # Setup OpenAI
        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.ai_enabled = False
        self.openai_client = None

        if api_key:
            # Clean API key (remove quotes if present)
            api_key = api_key.strip().strip('"').strip("'")
            
            try:
                # Check OpenAI library version for compatibility
                import openai as openai_lib
                openai_version = getattr(openai_lib, '__version__', 'unknown')
                print(f"   📦 OpenAI library version: {openai_version}")
                
                # Save and temporarily clear ALL potential proxy/environment variables
                # that might interfere with OpenAI initialization
                env_backup = {}
                problematic_vars = [
                    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
                    'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
                    'OPENAI_PROXY', 'OPENAI_API_BASE', 'OPENAI_ORG_ID'
                ]
                for var in problematic_vars:
                    if var in os.environ:
                        env_backup[var] = os.environ.pop(var)
                
                try:
                    # Method 1: Try with minimal initialization (no extra params)
                    # This works with most OpenAI library versions
                    import inspect
                    init_signature = inspect.signature(OpenAI.__init__)
                    params = list(init_signature.parameters.keys())
                    
                    # Only use parameters that definitely exist in the signature
                    init_kwargs = {'api_key': api_key}
                    
                    # Try to initialize
                    self.openai_client = OpenAI(**init_kwargs)
                    
                    # Test if client works by making a simple API call structure check
                    # (we don't actually call the API, just verify the client was created)
                    if hasattr(self.openai_client, 'chat') or hasattr(self.openai_client, 'models'):
                        self.ai_enabled = True
                        print("✅ OpenAI API configured successfully")
                    else:
                        raise Exception("OpenAI client created but doesn't have expected methods")
                        
                except TypeError as type_err:
                    error_str = str(type_err).lower()
                    if "proxies" in error_str or "unexpected keyword" in error_str:
                        # The library itself might be trying to use proxies internally
                        # Try importing and patching if possible
                        print(f"   ⚠️  OpenAI initialization error: {type_err}")
                        print("   💡 This is a known compatibility issue with some OpenAI versions")
                        print("   💡 Trying alternative initialization method...")
                        
                        # Last resort: Try using environment variable instead of parameter
                        os.environ['OPENAI_API_KEY'] = api_key
                        try:
                            # Initialize without api_key parameter (use env var)
                            self.openai_client = OpenAI()
                            self.ai_enabled = True
                            print("✅ OpenAI API configured (using environment variable method)")
                        except Exception as env_err:
                            # Remove the env var we just set
                            if 'OPENAI_API_KEY' in os.environ:
                                del os.environ['OPENAI_API_KEY']
                            raise env_err
                    else:
                        raise type_err
                        
                except Exception as init_err:
                    print(f"   ⚠️  OpenAI initialization failed: {init_err}")
                    raise init_err
                    
                finally:
                    # Restore environment variables
                    os.environ.update(env_backup)
                    
            except Exception as e:
                error_msg = str(e).lower()
                print(f"⚠️  OpenAI initialization failed: {e}")
                
                if "proxies" in error_msg:
                    print("   💡 Known issue: OpenAI library proxy parameter conflict")
                    print("   💡 Solution options:")
                    print("      1. Upgrade OpenAI: pip install --upgrade openai")
                    print("      2. Or downgrade: pip install 'openai<1.0'")
                    print("      3. Or use: pip install openai==1.12.0")
                else:
                    print("   💡 Try: pip install --upgrade openai")
                    print("   💡 Or: pip install 'openai>=1.0,<2.0'")
                
                print("   ⚠️  AI responses will be disabled")
                self.ai_enabled = False
                self.openai_client = None
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
        self.last_messages: Dict[str, str] = {}  # Legacy text-based tracking
        self.seen_message_ids: Dict[str, set] = {}  # New ID-based tracking
        self.monitored_contacts: List[str] = []
        
        # Automatic monitoring
        self.auto_monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_stopped_contacts: set = set()  # Contacts that have monitoring stopped
        self.monitoring_check_interval = 5  # Check every 5 seconds
        self.monitoring_lock = threading.Lock()  # Lock for thread-safe operations

        # Statistics
        self.messages_sent = 0
        self.messages_failed = 0
        self.messages_delivered = 0
        self.messages_read = 0
        self.ai_responses_sent = 0

        # Leads tracking
        self.leads_file = Path.cwd() / "confirmed_leads.csv"
        self._initialize_leads_file()

        # Setup browser
        self.driver = None
        self.wait = None
        self._setup_browser(headless)

    def _setup_browser(self, headless: bool = False):
        """Setup Chrome browser with WhatsApp Web"""
        print("🌐 Setting up browser...")

        # First, check if Chrome is installed
        import shutil
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
            "/usr/bin/google-chrome",  # Linux
            "/usr/bin/chromium-browser",  # Linux Chromium
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows 32-bit
        ]
        
        chrome_binary = None
        for path in chrome_paths:
            if Path(path).exists():
                chrome_binary = path
                print(f"   ✅ Found Chrome at: {chrome_binary}")
                break
        
        # Also try to find Chrome using 'which' command (for PATH)
        if not chrome_binary:
            for cmd in ["google-chrome", "chromium-browser", "chromium", "chrome"]:
                chrome_path = shutil.which(cmd)
                if chrome_path:
                    chrome_binary = chrome_path
                    print(f"   ✅ Found Chrome in PATH: {chrome_binary}")
                    break
        
        if not chrome_binary:
            print("   ⚠️  Chrome not found in standard locations")
            print("   💡 Attempting to use default Chrome installation...")
        else:
            print(f"   📍 Using Chrome binary: {chrome_binary}")

        # Chrome options
        options = webdriver.ChromeOptions()
        
        # Explicitly set Chrome binary path if found
        if chrome_binary:
            options.binary_location = chrome_binary

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
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            # Auto-install ChromeDriver with retry and better error handling
            print("   Installing/checking ChromeDriver...")
            service = None
            try:
                # Try to install ChromeDriver (may download if needed)
                driver_path = ChromeDriverManager().install()
                service = Service(driver_path)
                print(f"   ✅ ChromeDriver found at: {driver_path}")
            except Exception as driver_error:
                error_msg = str(driver_error).lower()
                if "could not reach host" in error_msg or "offline" in error_msg or "network" in error_msg:
                    print("   ⚠️  Network issue while downloading ChromeDriver")
                    print("   💡 Trying to find ChromeDriver in system PATH...")
                    # Try to find chromedriver in PATH
                    chromedriver_path = shutil.which("chromedriver")
                    if chromedriver_path:
                        service = Service(chromedriver_path)
                        print(f"   ✅ Found ChromeDriver in PATH: {chromedriver_path}")
                    else:
                        print("   ⚠️  ChromeDriver not found in PATH")
                        print("   💡 Creating service without explicit path (will use system default)")
                        # Don't specify service - let Selenium find it
                        service = None
                else:
                    print(f"   ⚠️  ChromeDriver error: {driver_error}")
                    # Try to continue without explicit service
                    service = None
            
            # Create Chrome driver instance - explicitly use Chrome, not Firefox
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                # Try without service - Selenium will attempt to find ChromeDriver
                print("   ⚠️  Attempting to launch Chrome without explicit ChromeDriver path...")
                self.driver = webdriver.Chrome(options=options)
            
            # Verify we're actually using Chrome (not Firefox or another browser)
            try:
                browser_name = self.driver.capabilities.get('browserName', 'unknown')
                if browser_name.lower() != 'chrome':
                    raise Exception(f"Wrong browser detected: {browser_name}. Expected Chrome.")
                print(f"   ✅ Confirmed: Using {browser_name.capitalize()} browser")
            except Exception as verify_error:
                print(f"   ⚠️  Could not verify browser: {verify_error}")
                # Continue anyway - might still work

            # Stealth modifications
            try:
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": self.driver.execute_script("return navigator.userAgent").replace('Headless', '')
                })
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
            except Exception as stealth_error:
                # Stealth modifications are optional, continue if they fail
                print(f"   ⚠️  Could not apply stealth modifications: {stealth_error}")
                print("   ℹ️  Continuing without stealth modifications...")

            self.wait = WebDriverWait(self.driver, 20)
            print("✅ Browser setup complete")

            # Login to WhatsApp Web
            self._login_whatsapp()

        except Exception as e:
            error_msg = str(e).lower()
            if "could not reach host" in error_msg or "offline" in error_msg:
                print(f"❌ Browser setup failed: Network connection issue")
                print(f"   Error details: {e}")
                print("   💡 Please check:")
                print("      1. Your internet connection")
                print("      2. Firewall settings (may be blocking ChromeDriver downloads)")
                print("      3. Try running: pip install --upgrade webdriver-manager")
                print("      4. Or manually install ChromeDriver from: https://chromedriver.chromium.org/")
            else:
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

    def _initialize_leads_file(self):
        """Initialize the leads CSV file with headers if it doesn't exist"""
        if not self.leads_file.exists():
            with open(self.leads_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'phone',
                    'name',
                    'city',
                    'product_confirmed',
                    'conversation_summary',
                    'status'
                ])
            print(f"✅ Created leads file: {self.leads_file}")

    def save_lead(self, phone: str, product: str, conversation_summary: str = ""):
        """
        Save a confirmed lead to the CSV file

        Args:
            phone: Customer phone number
            product: Product name that was confirmed
            conversation_summary: Brief summary of the conversation
        """
        try:
            # Lookup customer data from contacts_df
            name = "Customer"
            city = ""

            if self.contacts_df is not None:
                try:
                    # Format phone for matching (convert Arabic numerals, remove +, spaces, etc.)
                    phone_clean = convert_arabic_numerals(phone)
                    phone_clean = phone_clean.replace('+', '').replace(' ', '').replace('-', '')

                    # Try to find customer in contacts_df
                    # Match by phone number (checking both formatted and unformatted versions)
                    match_found = False
                    for idx, row in self.contacts_df.iterrows():
                        row_phone = str(row.get('phone_formatted', row.get('phone', '')))
                        row_phone = convert_arabic_numerals(row_phone)
                        row_phone = row_phone.replace('+', '').replace(' ', '').replace('-', '')
                        if phone_clean in row_phone or row_phone in phone_clean:
                            name = str(row.get('name', 'Customer'))
                            # The 'address' column in e-commerce CSV is actually the city
                            city = str(row.get('address', ''))
                            match_found = True
                            print(f"✅ Found customer in contacts: {name} from {city}")
                            break

                    if not match_found:
                        print(f"⚠️  Customer {phone} not found in contacts CSV - using defaults")
                except Exception as lookup_err:
                    print(f"⚠️  Error looking up customer data: {lookup_err}")

            # Get timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Append to CSV
            with open(self.leads_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    phone,
                    name,
                    city,
                    product,
                    conversation_summary,
                    'pending'
                ])

            print(f"✅ Lead saved: {name} ({phone}) from {city} - {product}")

        except Exception as e:
            print(f"⚠️  Failed to save lead: {e}")

    def get_leads(self) -> List[Dict]:
        """
        Read all leads from the CSV file

        Returns:
            List of lead dictionaries
        """
        leads = []
        try:
            if self.leads_file.exists():
                with open(self.leads_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    leads = list(reader)
        except Exception as e:
            print(f"⚠️  Failed to read leads: {e}")
        return leads

    def update_lead_status(self, phone: str, status: str):
        """
        Update the status of a lead

        Args:
            phone: Customer phone number
            status: New status (pending/contacted/converted/rejected)
        """
        try:
            leads = self.get_leads()

            # Update the status
            updated = False
            for lead in leads:
                if lead['phone'] == phone:
                    lead['status'] = status
                    updated = True
                    break

            if not updated:
                print(f"⚠️  Lead not found for {phone}")
                return

            # Write back to CSV
            with open(self.leads_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'phone', 'name', 'city', 'product_confirmed',
                    'conversation_summary', 'status'
                ])
                writer.writeheader()
                writer.writerows(leads)

            print(f"✅ Lead status updated: {phone} -> {status}")

        except Exception as e:
            print(f"⚠️  Failed to update lead status: {e}")

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

            # Check if this is the first time we're contacting this customer (initial offer)
            is_first_contact = phone not in self.monitored_contacts
            
            # If this is the first contact, start monitoring BEFORE sending (clears history and marks existing messages as seen)
            if is_first_contact:
                self.monitored_contacts.append(phone)
                self.start_monitoring_contact(phone)
            
            # Send media if provided
            if media_path and os.path.exists(media_path):
                media_result = self._send_media(media_path, message)
                if media_result:
                    # Media sent successfully
                    print(f"✅ Message with media sent to {phone}")
                    self.messages_sent += 1
                    
                    # If this is the first contact, add offer message to conversation history
                    # (History was already cleared in start_monitoring_contact above)
                    if is_first_contact:
                        # Add our offer message (caption if media, or full message) as assistant message
                        self.conversations[phone].append({
                            "role": "assistant",
                            "content": message if message else f"[Media: {Path(media_path).name}]"
                        })
                        print(f"   Added offer message to conversation history for {phone}")
                        
                        # Automatically start background monitoring if not already running
                        if not self.auto_monitoring_active:
                            self.start_auto_monitoring()
                        else:
                            print(f"   ✅ Auto-monitoring is already active for this contact")
                    # If already in monitoring, this is an AI response - don't modify history
                    # (History is already managed in generate_ai_response)
                    
                    return True
                else:
                    # Media send had issues, but might have still sent
                    # Check if we should fall back to text
                    print("⚠️  Media verification uncertain - message may have been sent")
                    print("💡 Skipping text fallback to avoid duplicate messages")
                    # Mark as sent anyway - user can check WhatsApp
                    self.messages_sent += 1
                    
                    # If this is the first contact, add offer message to conversation history
                    # (History was already cleared in start_monitoring_contact above)
                    if is_first_contact:
                        # Add our offer message as assistant message
                        self.conversations[phone].append({
                            "role": "assistant",
                            "content": message if message else f"[Media: {Path(media_path).name}]"
                        })
                        print(f"   Added offer message to conversation history for {phone}")
                        
                        # Automatically start background monitoring if not already running
                        if not self.auto_monitoring_active:
                            self.start_auto_monitoring()
                        else:
                            print(f"   ✅ Auto-monitoring is already active for this contact")
                    # If already in monitoring, this is an AI response - don't modify history
                    
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

            # If this is the first contact, add offer message to conversation history
            # (History was already cleared in start_monitoring_contact above)
            if is_first_contact:
                # Add our offer message as assistant message (from bot)
                self.conversations[phone].append({
                    "role": "assistant",
                    "content": message
                })
                print(f"   Added offer message to conversation history for {phone}")
                
                # Automatically start background monitoring if not already running
                if not self.auto_monitoring_active:
                    self.start_auto_monitoring()
                else:
                    print(f"   ✅ Auto-monitoring is already active for this contact")
            # If already in monitoring, this is an AI response - don't modify history
            # (History is already managed in generate_ai_response)

            return True

        except Exception as e:
            print(f"❌ Error sending to {phone}: {e}")
            self.messages_failed += 1
            return False

    def _send_text(self, message: str) -> bool:
        """Send text message with proper line break handling using system clipboard"""
        try:
            import pyperclip

            # Find message input box
            input_box = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
            )

            # Focus the input box
            input_box.click()
            time.sleep(0.5)

            # Copy message to system clipboard
            # This preserves line breaks exactly as they are
            pyperclip.copy(message)
            print(f"📋 Copied message to clipboard ({len(message)} chars, {message.count(chr(10))} line breaks)")

            # Paste using Ctrl+V (Cmd+V on Mac)
            # This is the most reliable way - same as manual paste
            import platform
            if platform.system() == 'Darwin':  # macOS
                input_box.send_keys(Keys.COMMAND, 'v')
            else:  # Windows/Linux
                input_box.send_keys(Keys.CONTROL, 'v')

            time.sleep(1)

            # Verify content was pasted
            content_check = self.driver.execute_script(
                """
                const el = arguments[0];
                return el.textContent || el.innerText || '';
                """,
                input_box
            )
            print(f"✓ Content in input box: {len(content_check)} chars")

            # Send the message with Enter
            input_box.send_keys(Keys.RETURN)
            time.sleep(1)

            return True

        except ImportError:
            print("⚠️  pyperclip not installed. Installing...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyperclip"])
            print("✓ pyperclip installed. Please try sending again.")
            return False
        except Exception as e:
            print(f"⚠️  Error sending text: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _send_media(self, media_path: str, caption: str = "") -> bool:
        """Send media (image/video) with optional caption using drag-and-drop for video preview"""
        try:
            print(f"📎 Attaching media: {Path(media_path).name}")

            # CRITICAL: Ensure window is visible and focused
            # File uploads don't work reliably when window is minimized/background
            print("🔍 Ensuring browser window is visible and focused...")
            try:
                # Maximize window (brings it to front)
                self.driver.maximize_window()

                # Switch to WhatsApp tab if not already active
                self.driver.switch_to.window(self.driver.current_window_handle)

                # Bring window to front using JavaScript (platform-independent)
                self.driver.execute_script("window.focus();")

                time.sleep(0.5)  # Brief pause for window manager
                print("✅ Window focused and ready")
            except Exception as focus_err:
                print(f"⚠️  Could not focus window: {focus_err}")
                print("   File upload may fail if browser is minimized")

            # Get absolute path
            abs_path = str(Path(media_path).absolute())

            # Determine file type
            file_ext = Path(media_path).suffix.lower()
            is_video = file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.3gp']

            if is_video:
                print(f"🎬 Sending video with preview")
            else:
                print(f"🖼️ Sending image")

            # STEP 1: Add caption FIRST (before attaching media)
            # When media is attached, WhatsApp will use this text as the caption
            if caption:
                print(f"📝 Typing caption first (will become media caption)...")
                try:
                    import pyperclip
                    import platform

                    input_box = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[contenteditable='true'][data-tab='10']"))
                    )

                    # Focus input box
                    input_box.click()
                    time.sleep(0.3)

                    # Use system clipboard to preserve line breaks
                    pyperclip.copy(caption)
                    print(f"📋 Caption copied to clipboard ({len(caption)} chars, {caption.count(chr(10))} line breaks)")

                    # Paste with Ctrl+V or Cmd+V
                    if platform.system() == 'Darwin':  # macOS
                        input_box.send_keys(Keys.COMMAND, 'v')
                    else:  # Windows/Linux
                        input_box.send_keys(Keys.CONTROL, 'v')

                    print(f"✅ Caption pasted in chat input: {caption[:50]}...")
                    time.sleep(1)

                    # Verify caption was pasted
                    caption_check = self.driver.execute_script(
                        """
                        const el = arguments[0];
                        return el.textContent || el.innerText || '';
                        """,
                        input_box
                    )
                    print(f"✓ Caption in input box: {len(caption_check)} chars")

                except Exception as e:
                    print(f"⚠️  Could not paste caption: {e}")
                    import traceback
                    traceback.print_exc()

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

                # Give menu time to fully render
                time.sleep(1)

                # Method 1: Try multiple icon selectors
                photos_clicked = False
                icon_selectors = [
                    "[data-icon='media-filled-refreshed']",
                    "[data-icon='image']",
                    "[data-icon='gallery']",
                    "span[data-icon='image']",
                    "span[data-icon='gallery']",
                ]

                for selector in icon_selectors:
                    try:
                        media_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if media_btn and media_btn.is_displayed():
                            media_btn.click()
                            print(f"✅ Clicked 'Photos & Videos' ({selector})")
                            photos_clicked = True
                            time.sleep(1.5)
                            break
                    except:
                        continue

                # Method 2: JavaScript with more comprehensive search
                if not photos_clicked:
                    photos_clicked = self.driver.execute_script("""
                        // Try icon selectors
                        const iconSelectors = [
                            '[data-icon="media-filled-refreshed"]',
                            '[data-icon="image"]',
                            '[data-icon="gallery"]',
                            'span[data-icon="image"]',
                            'span[data-icon="gallery"]'
                        ];

                        for (const sel of iconSelectors) {
                            const icon = document.querySelector(sel);
                            if (icon && icon.offsetParent !== null) {
                                // Find clickable parent
                                let clickable = icon;
                                while (clickable && !clickable.onclick && clickable.tagName !== 'BUTTON' && !clickable.getAttribute('role')) {
                                    clickable = clickable.parentElement;
                                }
                                if (clickable) {
                                    clickable.click();
                                    return true;
                                }
                            }
                        }

                        // Fallback: Look for menu items with photo/video text
                        const items = Array.from(document.querySelectorAll('li, div[role="button"], span[role="button"], button'));
                        for (const item of items) {
                            const text = (item.textContent || '').toLowerCase();
                            const label = (item.getAttribute('aria-label') || '').toLowerCase();
                            const title = (item.getAttribute('title') || '').toLowerCase();

                            if ((text.includes('photo') && text.includes('video')) ||
                                (label.includes('photo') && label.includes('video')) ||
                                (title.includes('photo') && title.includes('video')) ||
                                text.includes('photos & videos') ||
                                label.includes('photos & videos') ||
                                text.includes('images') ||
                                label.includes('images')) {
                                item.click();
                                return true;
                            }
                        }

                        // Last resort: click first menu item (usually Photos & Videos)
                        const firstItem = document.querySelector('ul li:first-child, div[role="button"]:first-of-type');
                        if (firstItem) {
                            firstItem.click();
                            return true;
                        }

                        return false;
                    """)

                    if photos_clicked:
                        print("✅ Clicked 'Photos & Videos' (via JavaScript)")
                        time.sleep(2.5)  # Increased wait for file input to be created

                if not photos_clicked:
                    print("⚠️  Could not find 'Photos & Videos' button, trying direct file input")
                    print("💡  This may cause video upload to fail")

            # Find file input - IMPORTANT: Wait longer for Finder to open and file input to be ready
            print("📂 Looking for file input...")
            time.sleep(3)  # Increased wait for file picker to fully load

            # Try to find the file input (it appears after clicking attach or Photos & Videos)
            # For videos, we want the file input that accepts video files
            if is_video:
                # For videos, be more strict - only use video or general file inputs
                file_input_selectors = [
                    "input[type='file'][accept*='video']",  # Video input preferred
                    "input[type='file']:not([accept*='image'])",  # General file input (not image-only)
                    "input[type='file']"  # Last resort: any file input
                ]
            else:
                # For images, image or general inputs are fine
                file_input_selectors = [
                    "input[type='file'][accept*='image']",
                    "input[type='file']"
                ]

            file_input = None
            found_selector = None
            for selector in file_input_selectors:
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if inputs:
                        # Get ALL file inputs and find the one that's most likely to be the right one
                        for inp in reversed(inputs):  # Check from last to first (newest first)
                            try:
                                # Check if input is attached to DOM and not hidden
                                if inp.is_enabled():
                                    # Check accept attribute
                                    accept_attr = inp.get_attribute('accept') or ''

                                    # For videos, MODIFY if it ONLY accepts images
                                    if is_video and accept_attr and 'video' not in accept_attr and 'image' in accept_attr:
                                        print(f"   🔧 Found image-only input: {accept_attr}")
                                        print(f"   🔧 Modifying to accept videos...")
                                        # Use JavaScript to modify the accept attribute
                                        self.driver.execute_script(
                                            "arguments[0].setAttribute('accept', 'image/*,video/*');",
                                            inp
                                        )
                                        accept_attr = inp.get_attribute('accept')
                                        print(f"   ✅ Modified to: {accept_attr}")

                                    file_input = inp
                                    found_selector = selector
                                    print(f"✅ Found file input: {selector}")
                                    if accept_attr:
                                        print(f"   Accepts: {accept_attr}")
                                    break
                            except Exception as ex:
                                print(f"   ⚠️  Error: {str(ex)}")
                                continue
                        if file_input:
                            break
                except:
                    continue

            if not file_input:
                # Last resort: wait for any file input to appear and filter properly
                try:
                    print("🔄 Waiting for file inputs to load...")
                    time.sleep(2)  # Give more time for inputs to appear

                    # Get ALL file inputs and find the best match
                    all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

                    if not all_inputs:
                        raise Exception("No file inputs found")

                    print(f"   Found {len(all_inputs)} file input(s), checking compatibility...")

                    for inp in reversed(all_inputs):  # Check newest first
                        try:
                            if not inp.is_enabled():
                                continue

                            accept_attr = inp.get_attribute('accept') or ''

                            # For videos, MODIFY image-only inputs to accept videos
                            if is_video:
                                if accept_attr and 'video' not in accept_attr and 'image' in accept_attr:
                                    print(f"   🔧 Found image-only input: {accept_attr}")
                                    print(f"   🔧 Modifying to accept videos...")
                                    # Use JavaScript to modify the accept attribute
                                    self.driver.execute_script(
                                        "arguments[0].setAttribute('accept', 'image/*,video/*');",
                                        inp
                                    )
                                    new_accept = inp.get_attribute('accept')
                                    print(f"   ✅ Modified accept attribute to: {new_accept}")
                                    file_input = inp
                                    break
                                # Accept inputs that explicitly allow video OR have no restrictions
                                elif not accept_attr or 'video' in accept_attr or ('image' not in accept_attr):
                                    file_input = inp
                                    print(f"✅ Found suitable file input - Accepts: {accept_attr or 'any file type'}")
                                    break
                            else:
                                # For images/documents, any input is fine
                                file_input = inp
                                print(f"✅ Found file input - Accepts: {accept_attr or 'any file type'}")
                                break
                        except Exception as inner_ex:
                            print(f"   ⚠️  Error checking input: {str(inner_ex)}")
                            continue

                    if not file_input:
                        raise Exception(f"Could not find suitable file input for {'video' if is_video else 'file'}")

                except Exception as e:
                    raise Exception(f"Could not find file input element: {str(e)}")

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

            # Ensure window is visible (message detection can fail when minimized)
            try:
                self.driver.maximize_window()
                self.driver.execute_script("window.focus();")
            except:
                pass  # Not critical for message checking

            # Open chat
            url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
            self.driver.get(url)
            time.sleep(5)  # Increased wait time for chat to load

            # Check if chat loaded successfully - try multiple selectors
            chat_loaded = False
            chat_selectors = [
                "[data-testid='conversation-panel-body']",
                "[data-testid='conversation-panel-messages']",
                "div[class*='_ak'][role='application']",  # Main WhatsApp panel
                "[contenteditable='true'][data-tab='10']",  # Message input box
            ]

            print("⏳ Waiting for chat to load...")
            for selector in chat_selectors:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if element:
                        print(f"✅ Chat loaded (found: {selector})")
                        chat_loaded = True
                        break
                except TimeoutException:
                    continue

            if not chat_loaded:
                # Last resort: check with JavaScript
                print("🔄 Trying JavaScript check...")
                chat_loaded = self.driver.execute_script("""
                    // Check if we're in a chat conversation
                    const hasMessages = document.querySelector('[data-testid="msg-container"]') !== null;
                    const hasInputBox = document.querySelector('[contenteditable="true"][data-tab="10"]') !== null;
                    const hasConversation = document.querySelector('[role="application"]') !== null;
                    return hasMessages || hasInputBox || hasConversation;
                """)

            if not chat_loaded:
                print(f"⚠️  Could not load chat for {phone} - chat interface not detected")
                print("💡 Tip: Make sure the chat exists and WhatsApp Web is properly loaded")
                return None

            # Scroll to ensure all recent messages are loaded
            print("📜 Scrolling to load recent messages...")
            try:
                self.driver.execute_script("""
                    // Find the message container and scroll to bottom
                    const msgContainer = document.querySelector('[data-testid="conversation-panel-body"]') ||
                                        document.querySelector('[data-testid="conversation-panel-messages"]');
                    if (msgContainer) {
                        msgContainer.scrollTop = msgContainer.scrollHeight;
                        console.log('Scrolled to bottom of messages');
                    } else {
                        console.log('Could not find message container to scroll');
                    }
                """)
                time.sleep(2)  # Increased: Wait for messages to render after scroll
            except Exception as scroll_err:
                print(f"⚠️  Could not scroll: {scroll_err}")

            # Give EXTRA time for messages to fully render (critical for minimized window)
            print("⏳ Waiting for messages to render...")
            time.sleep(2.5)  # Increased from 1.5s

            # Try multiple strategies to find incoming messages
            last_msg = None
            all_incoming = []

            # Strategy 1: Use JavaScript to find incoming messages with timestamps/IDs
            # This is MORE ROBUST - tracks messages by their unique attributes
            result = self.driver.execute_script(r"""
                console.log('Starting message detection...');

                // Try multiple selectors for message containers
                let messageContainers = document.querySelectorAll('[data-testid="msg-container"]');
                console.log('Method 1 - Found containers with [data-testid="msg-container"]:', messageContainers.length);

                // Fallback: try alternative selectors
                if (messageContainers.length === 0) {
                    messageContainers = document.querySelectorAll('div[data-id]');
                    console.log('Method 2 - Found containers with div[data-id]:', messageContainers.length);
                }

                // Filter for incoming messages (not sent by us)
                const incomingMessages = [];

                for (const container of messageContainers) {
                    // Check if this is an incoming message (has 'message-in' class)
                    // WhatsApp uses 'message-in' for received messages and 'message-out' for sent
                    const msgDiv = container.querySelector('[class*="message-in"]');

                    if (msgDiv) {
                        console.log('Found incoming message element');
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
                            // Get timestamp if available
                            let timestamp = null;
                            const timeEl = container.querySelector('[data-testid="msg-meta"]') ||
                                          container.querySelector('span[class*="timestamp"]') ||
                                          container.querySelector('div[data-pre-plain-text]');
                            if (timeEl) {
                                timestamp = timeEl.textContent || timeEl.getAttribute('data-pre-plain-text');
                            }

                            // Create unique ID from message content + timestamp
                            const msgId = container.getAttribute('data-id') ||
                                         (text.substring(0, 50) + (timestamp || '')).replace(/\s/g, '');

                            incomingMessages.push({
                                text: text.trim(),
                                timestamp: timestamp,
                                id: msgId
                            });
                        }
                    }
                }

                console.log('Incoming messages found:', incomingMessages.length);

                // Return all incoming messages
                return {
                    messages: incomingMessages,
                    count: incomingMessages.length
                };
            """)

            if result:
                messages = result.get('messages', [])
                msg_count = result.get('count', 0)
                print(f"📨 JavaScript found {msg_count} incoming messages in chat with {phone}")
                if msg_count == 0:
                    print("⚠️  JavaScript found 0 messages - will try fallback method")

                # Get seen message IDs for this phone
                if not hasattr(self, 'seen_message_ids'):
                    self.seen_message_ids = {}
                if phone not in self.seen_message_ids:
                    self.seen_message_ids[phone] = set()

                # Find NEW messages (ones we haven't seen before)
                new_messages = []
                for msg in messages:
                    msg_id = msg.get('id', '')
                    msg_text = msg.get('text', '')
                    if msg_id and msg_id not in self.seen_message_ids[phone]:
                        new_messages.append(msg)
                        print(f"  ✨ NEW: {msg_text[:60]}..." if len(msg_text) > 60 else f"  ✨ NEW: {msg_text}")

                # If we found new messages, mark them as seen and return the FIRST new one
                if new_messages:
                    # Mark ALL new messages as seen
                    for msg in new_messages:
                        self.seen_message_ids[phone].add(msg.get('id', ''))

                    # Keep only last 100 message IDs to avoid memory bloat
                    if len(self.seen_message_ids[phone]) > 100:
                        # Convert to list, keep last 100, convert back to set
                        self.seen_message_ids[phone] = set(list(self.seen_message_ids[phone])[-100:])

                    # Return the FIRST new message (oldest unread)
                    last_msg = new_messages[0].get('text', '')
                    print(f"✨ Returning FIRST new message from {phone}: {last_msg[:100]}...")

                    # Also update the old tracking for backward compatibility
                    if last_msg:
                        self.last_messages[phone] = last_msg
                else:
                    print(f"ℹ️  All messages already seen")
                    all_incoming = []  # Clear to trigger fallback

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
                                # Use text-based tracking as fallback
                                last_seen = self.last_messages.get(phone, "")
                                if last_msg != last_seen:
                                    self.last_messages[phone] = last_msg
                                    print(f"✨ NEW MESSAGE from {phone}: {last_msg[:100]}...")
                                    return last_msg
                                else:
                                    print(f"ℹ️  No new messages (already seen)")
                                    return None
                    except Exception as sel_err:
                        continue

            if not last_msg:
                print(f"ℹ️  No new messages from {phone}")
                return None

            # If we got here, last_msg is already set from the ID-based method
            return last_msg

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
        import sys
        print(f"\n🤖 Generating AI response for message from {phone}...", flush=True)
        sys.stdout.flush()  # Force immediate output
        print(f"   Customer: {message[:100]}..." if len(message) > 100 else f"   Customer: {message}", flush=True)
        sys.stdout.flush()

        if not self.ai_enabled:
            print("⚠️  AI not enabled - using default response", flush=True)
            sys.stdout.flush()
            return "Thank you for your message. We'll get back to you soon."

        try:
            # Get conversation history
            history = self.conversations.get(phone, [])
            print(f"   Using {len(history)} previous messages as context", flush=True)
            sys.stdout.flush()

            # Build messages for API
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]

            # Add history (last 10 messages)
            messages.extend(history[-10:])

            # Add current message
            messages.append({"role": "user", "content": message})

            print(f"   Calling OpenAI {self.model}...", flush=True)
            sys.stdout.flush()

            # Call OpenAI API with explicit timeout
            # Increased max_tokens to 800 to prevent message truncation
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=800,  # Increased from 200 to allow complete responses
                timeout=30.0  # 30 second timeout
            )

            print(f"   ✅ Received response from OpenAI", flush=True)
            sys.stdout.flush()

            ai_response = response.choices[0].message.content.strip()
            
            # Check if response was truncated or appears incomplete
            finish_reason = response.choices[0].finish_reason
            needs_completion = False
            
            # Detect if response was cut off
            if finish_reason == "length":
                needs_completion = True
                print(f"   ⚠️  Response hit token limit, requesting completion...", flush=True)
                sys.stdout.flush()
            elif ai_response and len(ai_response) > 20:
                # Detect incomplete responses that don't have finish_reason="length" but are still cut off
                # Common patterns: ends with single digit, incomplete list item, no proper punctuation
                response_stripped = ai_response.strip()
                response_end = response_stripped[-1] if response_stripped else ''
                response_second_last = response_stripped[-2] if len(response_stripped) >= 2 else ''
                
                # Check if response ends with incomplete pattern
                # Ends with single digit (not part of "1:" or "2:" pattern)
                ends_with_single_digit = (
                    len(ai_response) > 50 and 
                    response_end.isdigit() and 
                    response_second_last != ':' and
                    response_second_last != '.' and
                    not (len(response_stripped) >= 3 and response_stripped[-3] == ':')  # Not "1:" pattern
                )
                
                # Ends without proper punctuation
                ends_without_punctuation = (
                    response_end not in ['.', '!', '?', ':', ';', '،', '。', ')', ']', '}'] and 
                    not ai_response.endswith('...') and
                    len(ai_response) > 100
                )
                
                # Ends with digit after newlines (incomplete list item)
                ends_with_incomplete_list = (
                    ai_response.count('\n') > 2 and 
                    response_end.isdigit() and 
                    ':\n' not in ai_response[-30:]  # No complete list items in last 30 chars
                )
                
                # If response looks incomplete, request completion
                if ends_with_single_digit or ends_with_incomplete_list or ends_without_punctuation:
                    # For single digit endings, almost always incomplete (like ending with just "1")
                    if ends_with_single_digit or ends_with_incomplete_list:
                        needs_completion = True
                        print(f"   ⚠️  Response appears incomplete (ends with: '{ai_response[-30:]}'), requesting completion...", flush=True)
                        sys.stdout.flush()
                    # For missing punctuation, only if it's a long response
                    elif ends_without_punctuation and len(ai_response) > 150:
                        # Check if last sentence ending is far back
                        last_sentence_end = max(
                            ai_response.rfind('.'),
                            ai_response.rfind('!'),
                            ai_response.rfind('?'),
                            ai_response.rfind(':\n'),
                        )
                        # If last sentence end is more than 100 chars back, likely incomplete
                        if last_sentence_end < len(ai_response) - 100:
                            needs_completion = True
                            print(f"   ⚠️  Response appears incomplete (no proper ending), requesting completion...", flush=True)
                            sys.stdout.flush()
            
            # If response needs completion, request continuation
            if needs_completion:
                # Request continuation to complete the message
                continuation_messages = messages + [{"role": "assistant", "content": ai_response}]
                continuation_messages.append({"role": "user", "content": "أكمل رسالتك من حيث توقفت. (Complete your message from where you left off.)"})
                
                try:
                    continuation_response = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=continuation_messages,
                        temperature=0.7,
                        max_tokens=400,
                        timeout=20.0
                    )
                    continuation = continuation_response.choices[0].message.content.strip()
                    # Only append if continuation makes sense (not a duplicate start)
                    if continuation and len(continuation) > 10:
                        ai_response = ai_response + " " + continuation
                        print(f"   ✅ Response completed", flush=True)
                        sys.stdout.flush()
                except Exception as e:
                    print(f"   ⚠️  Could not complete response: {e}", flush=True)
                    sys.stdout.flush()
                    # If we can't complete, clean up the incomplete ending
                    if ai_response:
                        # Remove incomplete sentences at the end
                        last_period = ai_response.rfind('.')
                        last_exclamation = ai_response.rfind('!')
                        last_question = ai_response.rfind('?')
                        last_colon = ai_response.rfind(':\n')  # For list items
                        last_complete = max(last_period, last_exclamation, last_question, last_colon)
                        
                        # Only trim if we can keep at least 70% of the message
                        if last_complete > len(ai_response) * 0.7:
                            ai_response = ai_response[:last_complete + 1].strip()
                            print(f"   ⚠️  Trimmed incomplete ending from response", flush=True)
                            sys.stdout.flush()
                        # If message ends with a single digit or incomplete pattern, try to remove it
                        elif ai_response[-1].isdigit() and len(ai_response) > 20:
                            # Find last proper sentence ending before the digit
                            before_digit = ai_response[:-1].rstrip()
                            last_proper_end = max(
                                before_digit.rfind('.'),
                                before_digit.rfind('!'),
                                before_digit.rfind('?'),
                                before_digit.rfind(':')
                            )
                            if last_proper_end > len(before_digit) * 0.6:
                                ai_response = before_digit[:last_proper_end + 1].strip()
                                print(f"   ⚠️  Removed incomplete ending pattern", flush=True)
                                sys.stdout.flush()
            
            print(f"✅ AI Response generated: {ai_response[:100]}..." if len(ai_response) > 100 else f"✅ AI Response: {ai_response}", flush=True)
            sys.stdout.flush()

            # Check for lead confirmation marker
            lead_confirmed = False
            product_name = ""
            clean_response = ai_response

            # Look for [LEAD_CONFIRMED: product_name] pattern
            lead_pattern = r'\[LEAD_CONFIRMED:\s*([^\]]+)\]'
            match = re.search(lead_pattern, ai_response)

            if match:
                lead_confirmed = True
                product_name = match.group(1).strip()
                # Remove the marker from the response
                clean_response = re.sub(lead_pattern, '', ai_response).strip()
                print(f"🎯 Lead confirmed! Product: {product_name}", flush=True)
                sys.stdout.flush()

                # Create conversation summary
                conversation_summary = f"Last message: {message[:100]}"

                # Save the lead
                self.save_lead(phone, product_name, conversation_summary)

            # Update conversation history (use clean response without marker)
            if phone not in self.conversations:
                self.conversations[phone] = []

            self.conversations[phone].append({"role": "user", "content": message})
            self.conversations[phone].append({"role": "assistant", "content": clean_response})

            # Keep only last 20 messages
            if len(self.conversations[phone]) > 20:
                self.conversations[phone] = self.conversations[phone][-20:]

            print(f"   Conversation history updated ({len(self.conversations[phone])} messages)", flush=True)
            sys.stdout.flush()
            return clean_response

        except Exception as e:
            print(f"⚠️  AI response error: {e}", flush=True)
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return "Thank you for your message. We'll get back to you soon."

    def start_monitoring_contact(self, phone: str):
        """
        Start monitoring a contact - clears conversation history and marks existing messages as seen.
        Call this when you first add a contact to monitoring.

        Args:
            phone: Phone number to start monitoring
        """
        try:
            phone = self._format_phone(phone)
            print(f"🔄 Starting monitoring for {phone}...")

            # Clear any existing conversation history for this customer
            # This ensures we start fresh from our offer message
            if phone in self.conversations:
                print(f"   Clearing previous conversation history for {phone}")
                self.conversations[phone] = []
            else:
                # Initialize empty conversation history
                self.conversations[phone] = []

            # Mark all existing messages as "seen" to avoid responding to old messages
            try:
                # Open chat
                url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
                self.driver.get(url)
                time.sleep(3)

                # Use get_new_messages to populate seen_message_ids
                # This will mark all current messages as "seen"
                _ = self.get_new_messages(phone)
                print(f"   {len(self.seen_message_ids.get(phone, set()))} existing messages marked as seen")
            except Exception as e:
                print(f"   ⚠️  Could not mark existing messages as seen: {e}")

            print(f"✅ Monitoring started for {phone} - conversation history cleared")

        except Exception as e:
            print(f"⚠️  Error starting monitoring for {phone}: {e}")

    def _background_monitoring_loop(self):
        """Background thread that continuously monitors contacts for new messages"""
        print("🔄 Background monitoring thread started")
        
        while self.auto_monitoring_active:
            try:
                # Get list of contacts to monitor (thread-safe)
                with self.monitoring_lock:
                    # Only monitor contacts that are not stopped
                    active_contacts = [
                        phone for phone in self.monitored_contacts 
                        if phone not in self.monitoring_stopped_contacts
                    ]
                
                if not active_contacts:
                    # No contacts to monitor, wait a bit and check again
                    time.sleep(self.monitoring_check_interval)
                    continue
                
                # Check each contact for new messages
                for phone in active_contacts:
                    if not self.auto_monitoring_active:
                        break
                    
                    try:
                        # Check for new messages
                        new_msg = self.get_new_messages(phone)
                        
                        if new_msg:
                            print(f"\n📨 New message from {phone}!")
                            print(f"   Customer: {new_msg[:100]}...")
                            
                            # Generate AI response
                            if self.ai_enabled:
                                print(f"   🤖 Generating AI response...")
                                ai_response = self.generate_ai_response(new_msg, phone)
                                
                                # Send response
                                print(f"   📤 Sending AI response...")
                                if self.send_message(phone, ai_response):
                                    self.ai_responses_sent += 1
                                    print(f"   ✅ Response sent successfully to {phone}")
                                else:
                                    print(f"   ❌ Failed to send response to {phone}")
                            else:
                                print(f"   ⚠️  AI not enabled - skipping response")
                    
                    except Exception as e:
                        print(f"   ⚠️  Error checking/responding to {phone}: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Wait before next check cycle
                time.sleep(self.monitoring_check_interval)
                
            except Exception as e:
                print(f"⚠️  Error in background monitoring loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.monitoring_check_interval)
        
        print("🛑 Background monitoring thread stopped")

    def start_auto_monitoring(self):
        """Start automatic background monitoring for all monitored contacts"""
        with self.monitoring_lock:
            if self.auto_monitoring_active:
                print("ℹ️  Auto-monitoring is already active")
                return
            
            self.auto_monitoring_active = True
            
            # Start background monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._background_monitoring_loop,
                daemon=True,  # Daemon thread so it stops when main program exits
                name="AutoMonitoringThread"
            )
            self.monitoring_thread.start()
            print(f"✅ Auto-monitoring started (checking every {self.monitoring_check_interval} seconds)")
            print(f"   Monitoring {len(self.monitored_contacts)} contact(s)")

    def stop_auto_monitoring(self):
        """Stop automatic background monitoring"""
        with self.monitoring_lock:
            if not self.auto_monitoring_active:
                print("ℹ️  Auto-monitoring is not active")
                return
            
            self.auto_monitoring_active = False
            print("🛑 Stopping auto-monitoring...")
        
        # Wait for thread to finish (with timeout)
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        
        print("✅ Auto-monitoring stopped")

    def stop_monitoring_contact(self, phone: str):
        """Stop monitoring a specific contact"""
        phone = self._format_phone(phone)
        with self.monitoring_lock:
            if phone in self.monitoring_stopped_contacts:
                print(f"ℹ️  Monitoring already stopped for {phone}")
                return
            
            self.monitoring_stopped_contacts.add(phone)
            print(f"🛑 Stopped monitoring for {phone}")

    def resume_monitoring_contact(self, phone: str):
        """Resume monitoring a specific contact"""
        phone = self._format_phone(phone)
        with self.monitoring_lock:
            if phone not in self.monitoring_stopped_contacts:
                print(f"ℹ️  Monitoring not stopped for {phone}")
                return
            
            self.monitoring_stopped_contacts.remove(phone)
            print(f"▶️  Resumed monitoring for {phone}")

    def is_contact_monitoring_stopped(self, phone: str) -> bool:
        """Check if monitoring is stopped for a contact"""
        phone = self._format_phone(phone)
        with self.monitoring_lock:
            return phone in self.monitoring_stopped_contacts

    def initialize_message_tracking(self, phone: str):
        """
        Mark all existing messages from a contact as "seen" to avoid responding to old messages.
        Call this when you start monitoring a new contact.

        Args:
            phone: Phone number to initialize tracking for
        """
        try:
            phone = self._format_phone(phone)
            print(f"🔄 Initializing message tracking for {phone}...")

            # Open chat
            url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
            self.driver.get(url)
            time.sleep(5)

            # Use get_new_messages to populate seen_message_ids without returning anything
            # This will mark all current messages as "seen"
            _ = self.get_new_messages(phone)

            print(f"✅ Message tracking initialized for {phone}")
            print(f"   {len(self.seen_message_ids.get(phone, set()))} messages marked as seen")

        except Exception as e:
            print(f"⚠️  Error initializing tracking for {phone}: {e}")

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

        # Note: Conversation history is initialized when messages are sent (in send_message)
        # We don't clear it here to preserve the context starting from our offer message

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
        # Stop auto-monitoring if active
        if self.auto_monitoring_active:
            self.stop_auto_monitoring()
        
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
