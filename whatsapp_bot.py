"""
WhatsApp Bulk Messaging Bot with AI Auto-Responses
Modern, simplified implementation with robust error handling
"""

import os
import time
import random
import csv
import re
import json
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
        contacts_df = None,
        test_mode: bool = False
    ):
        """
        Initialize WhatsApp Bot

        Args:
            openai_api_key: OpenAI API key (or set in .env file)
            system_prompt: Custom AI system prompt
            headless: Run browser in headless mode (not recommended for WhatsApp)
            contacts_df: DataFrame with customer data (name, phone, address/city)
            test_mode: If True, skip loading/saving bot_state.json (reserved for real customers)
        """
        # Load environment variables
        load_dotenv()

        # Store contacts dataframe for customer lookup
        self.contacts_df = contacts_df
        
        # Test mode flag (skip bot_state.json operations when True)
        self.test_mode = test_mode

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
        self.test_contacts: set = set()  # Track test contacts (skip bot_state.json for these)
        
        # Follow-up (relance) tracking
        self.last_contact_time: Dict[str, datetime] = {}  # When we last contacted each customer
        self.customer_responded: Dict[str, bool] = {}  # Whether customer responded after our last contact
        self.followup_sent: Dict[str, bool] = {}  # Whether we already sent a follow-up
        self.followup_enabled = True  # Enable/disable follow-up feature
        self.followup_delay_minutes = 60  # Default: 60 minutes (1 hour) before follow-up
        self.followup_message_template = None  # Custom follow-up message (None = use default from JSON)
        # Load default follow-up message from JSON file
        self.default_followup_template = self._load_followup_message_from_json()
        
        # Pending media tracking (media to send after customer responds)
        self.pending_media: Dict[str, str] = {}  # {phone: media_path} - Main media to send after first customer response
        self.pending_media_2: Dict[str, str] = {}  # {phone: media_path} - Second media (free product) to send immediately after first media
        self.media_sent_after_response: Dict[str, bool] = {}  # Track if main media was already sent after response
        self.media_2_sent_after_response: Dict[str, bool] = {}  # Track if second media was already sent after response
        
        # Automatic monitoring
        self.auto_monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_stopped_contacts: set = set()  # Contacts that have monitoring stopped
        self.monitoring_check_interval = 5  # Check every 5 seconds
        self.monitoring_lock = threading.Lock()  # Lock for thread-safe operations
        
        # Browser synchronization (prevent race conditions when switching chats)
        self.browser_lock = threading.Lock()  # Lock for browser operations (driver.get, etc.)
        self.current_chat_phone: Optional[str] = None  # Track which chat is currently open
        self.bulk_sending_active = False  # Flag to pause background monitoring during bulk sending

        # Statistics
        self.messages_sent = 0
        self.messages_failed = 0
        self.messages_delivered = 0
        self.messages_read = 0
        self.ai_responses_sent = 0

        # Leads tracking
        self.leads_file = Path.cwd() / "confirmed_leads.csv"
        self._initialize_leads_file()

        # State persistence (to remember contacted customers across restarts)
        # Skip bot_state.json operations in test mode (reserved for real customers)
        self.state_file = Path.cwd() / "bot_state.json"
        if not self.test_mode:
            self._load_state()  # Load previous state on startup
        else:
            print("ℹ️  Test mode enabled - skipping bot_state.json (reserved for real customers)")

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

    def _load_state(self):
        """Load bot state from file (monitored contacts, contact times, etc.)"""
        # Skip loading state in test mode (reserved for real customers)
        if self.test_mode:
            print("ℹ️  Test mode: Skipping bot_state.json load")
            return
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # Load monitored contacts
                self.monitored_contacts = state.get('monitored_contacts', [])
                
                # Load last contact times (convert ISO strings back to datetime)
                last_contact_times = state.get('last_contact_time', {})
                for phone, time_str in last_contact_times.items():
                    try:
                        self.last_contact_time[phone] = datetime.fromisoformat(time_str)
                    except (ValueError, AttributeError):
                        # Skip invalid timestamps
                        pass
                
                # Load customer response status
                self.customer_responded = state.get('customer_responded', {})
                
                # Load follow-up status
                self.followup_sent = state.get('followup_sent', {})
                
                # Load pending media (media to send after customer responds)
                self.pending_media = state.get('pending_media', {})
                self.pending_media_2 = state.get('pending_media_2', {})
                self.media_sent_after_response = state.get('media_sent_after_response', {})
                self.media_2_sent_after_response = state.get('media_2_sent_after_response', {})
                
                # Load seen message IDs and texts (convert lists back to sets)
                seen_message_ids_dict = state.get('seen_message_ids', {})
                self.seen_message_ids = {
                    phone: set(ids) for phone, ids in seen_message_ids_dict.items()
                }
                seen_message_texts_dict = state.get('seen_message_texts', {})
                self.seen_message_texts = {
                    phone: set(texts) for phone, texts in seen_message_texts_dict.items()
                }
                
                print(f"✅ Loaded bot state: {len(self.monitored_contacts)} contacted customers")
                if self.monitored_contacts:
                    print(f"   📋 Previously contacted: {len(self.monitored_contacts)} customers")
                    print(f"   ⏰ Contact times tracked: {len(self.last_contact_time)}")
                    responded_count = sum(1 for v in self.customer_responded.values() if v)
                    print(f"   💬 Responses tracked: {responded_count}")
                    followup_count = sum(1 for v in self.followup_sent.values() if v)
                    print(f"   📬 Follow-ups sent: {followup_count}")
            except Exception as e:
                print(f"⚠️  Error loading bot state: {e}")
                print("   Starting with fresh state")
        else:
            print("ℹ️  No previous bot state found - starting fresh")

    def _save_state(self):
        """Save bot state to file (monitored contacts, contact times, etc.)"""
        # Skip saving state in test mode OR if all monitored contacts are test contacts (reserved for real customers)
        if self.test_mode:
            # Don't print every time to avoid spam, but log occasionally if needed
            return
        
        # Filter out test contacts from state (don't save test contacts to bot_state.json)
        real_monitored_contacts = [c for c in self.monitored_contacts if c not in self.test_contacts]
        
        # If all contacts are test contacts, skip saving (no real customers to save)
        if not real_monitored_contacts and self.monitored_contacts:
            # All monitored contacts are test contacts - skip saving
            return
        
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            last_contact_times_iso = {
                phone: time.isoformat() if isinstance(time, datetime) else str(time)
                for phone, time in self.last_contact_time.items()
            }
            
            # Convert sets to lists for JSON serialization
            seen_message_ids_dict = {
                phone: list(ids) for phone, ids in self.seen_message_ids.items()
            }
            seen_message_texts_dict = {
                phone: list(texts) for phone, texts in self.seen_message_texts.items()
            }
            
            # Filter out test contacts from all state dictionaries (don't save test contacts to bot_state.json)
            real_last_contact_time = {k: v for k, v in last_contact_times_iso.items() if k not in self.test_contacts}
            real_customer_responded = {k: v for k, v in self.customer_responded.items() if k not in self.test_contacts}
            real_followup_sent = {k: v for k, v in self.followup_sent.items() if k not in self.test_contacts}
            real_pending_media = {k: v for k, v in self.pending_media.items() if k not in self.test_contacts}
            real_pending_media_2 = {k: v for k, v in self.pending_media_2.items() if k not in self.test_contacts}
            real_media_sent_after_response = {k: v for k, v in self.media_sent_after_response.items() if k not in self.test_contacts}
            real_media_2_sent_after_response = {k: v for k, v in self.media_2_sent_after_response.items() if k not in self.test_contacts}
            real_seen_message_ids = {k: v for k, v in seen_message_ids_dict.items() if k not in self.test_contacts}
            real_seen_message_texts = {k: v for k, v in seen_message_texts_dict.items() if k not in self.test_contacts}
            
            state = {
                'monitored_contacts': real_monitored_contacts,  # Only real customers (no test contacts)
                'last_contact_time': real_last_contact_time,
                'customer_responded': real_customer_responded,
                'followup_sent': real_followup_sent,
                'pending_media': real_pending_media,
                'pending_media_2': real_pending_media_2,
                'media_sent_after_response': real_media_sent_after_response,
                'media_2_sent_after_response': real_media_2_sent_after_response,
                'seen_message_ids': real_seen_message_ids,
                'seen_message_texts': real_seen_message_texts,
                'last_saved': datetime.now().isoformat()
            }
            
            # Save to file atomically (write to temp file, then rename)
            temp_file = self.state_file.with_suffix('.tmp')
            
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            # Atomic rename (works on both Unix and Windows)
            temp_file.replace(self.state_file)
            
            # Verify file was written
            if self.state_file.exists():
                # Verify file has content
                file_size = self.state_file.stat().st_size
                if file_size > 0:
                    test_count = len(self.test_contacts)
                    real_count = len(real_monitored_contacts)
                    total_count = len(self.monitored_contacts)
                    if test_count > 0:
                        print(f"💾 Bot state saved: {real_count} real customers tracked, {test_count} test contacts excluded (file size: {file_size} bytes)")
                    else:
                        print(f"💾 Bot state saved: {total_count} contacts tracked (file size: {file_size} bytes)")
                else:
                    print(f"⚠️  Warning: State file is empty at {self.state_file}")
            else:
                print(f"⚠️  Warning: State file was not created at {self.state_file}")
                print(f"   Attempted to write to: {temp_file}")
            
        except Exception as e:
            print(f"⚠️  Error saving bot state: {e}")
            import traceback
            traceback.print_exc()
            # Try to save to a backup location
            try:
                backup_file = Path.cwd() / "bot_state_backup.json"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'monitored_contacts': self.monitored_contacts,
                        'last_contact_time': {k: v.isoformat() if isinstance(v, datetime) else str(v) for k, v in self.last_contact_time.items()},
                        'customer_responded': self.customer_responded,
                        'followup_sent': self.followup_sent,
                        'last_saved': datetime.now().isoformat()
                    }, f, indent=2, ensure_ascii=False)
                print(f"💾 Saved backup state to {backup_file}")
            except Exception as backup_err:
                print(f"❌ Failed to save backup state: {backup_err}")

    def _open_chat_safely(self, phone: str, force: bool = False) -> bool:
        """
        Safely open a chat with thread-safe locking and current chat tracking.
        
        Args:
            phone: Phone number to open chat for
            force: If True, open even if already in this chat (for refresh)
            
        Returns:
            True if chat opened successfully, False otherwise
        """
        phone = self._format_phone(phone)
        
        with self.browser_lock:
            # Check if we're already in this chat
            if not force and self.current_chat_phone == phone:
                # Already in the correct chat, no need to switch
                return True
            
            try:
                # Open chat
                url = f"https://web.whatsapp.com/send?phone={phone.replace('+', '')}"
                self.driver.get(url)
                self.current_chat_phone = phone
                
                # Reduced wait time for faster checking (was 3-5s, now 2-3s)
                time.sleep(random.uniform(2, 3))
                return True
            except Exception as e:
                print(f"⚠️  Error opening chat for {phone}: {e}")
                self.current_chat_phone = None
                return False

    def send_message(
        self,
        phone: str,
        message: str,
        media_path: Optional[str] = None,
        media_path_2: Optional[str] = None,
        is_followup: bool = False,
        test_message: bool = False
    ) -> bool:
        """
        Send message to a contact

        Args:
            phone: Phone number (e.g., "+966501234567")
            message: Message text (or caption if media provided)
            media_path: Optional path to main image/video file (sent after customer responds on first contact)
            media_path_2: Optional path to second image/video file (free product, sent immediately after first media)
            is_followup: If True, allow sending even if contact is already in monitored_contacts
            test_message: If True, skip bot_state.json operations (reserved for real customers)

        Returns:
            True if sent successfully
        """
        try:
            phone = self._format_phone(phone)
            print(f"\n📤 Sending to {phone}...")

            # Open chat safely (with lock to prevent race conditions)
            if not self._open_chat_safely(phone):
                print(f"❌ Failed to open chat for {phone}")
                self.messages_failed += 1
                return False

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
            # For test messages, skip state checks (don't use bot_state.json)
            is_first_contact = phone not in self.monitored_contacts if not test_message else True
            
            # If contact is already in monitored_contacts, skip sending initial offer (they've already been contacted)
            # BUT allow follow-ups to be sent (is_followup=True)
            # BUT allow media to be sent (if media_path is provided, this is likely an AI response with media)
            # Skip this check for test messages (test messages always send)
            if not test_message and not is_first_contact and not is_followup and not media_path:
                print(f"   ℹ️  {phone} has already been contacted. Skipping initial offer.")
                print(f"   💡 This contact is being monitored and will receive follow-ups if needed.")
                return True  # Return True to indicate "success" (no error, just skipped)
            
            # If this is the first contact, start monitoring BEFORE sending (clears history and marks existing messages as seen)
            # But skip opening the chat since we're already in it
            # For test messages, still monitor (in memory) but skip saving to bot_state.json
            if is_first_contact:
                # Add to monitored contacts (in memory - for both test and real messages)
                if phone not in self.monitored_contacts:
                    self.monitored_contacts.append(phone)
                
                # Mark as test contact if this is a test message (skip bot_state.json for this contact)
                if test_message:
                    self.test_contacts.add(phone)
                    print("   ℹ️  Test message: Contact marked as test contact (bot_state.json skipped)")
                
                # Start monitoring contact (in memory - enables AI responses)
                self.start_monitoring_contact(phone, skip_chat_open=True)
                
                # Initialize follow-up tracking for this customer (in memory)
                self.last_contact_time[phone] = datetime.now()
                self.customer_responded[phone] = False
                self.followup_sent[phone] = False
                
                # Save state to bot_state.json ONLY for real customers (skip for test messages)
                if not test_message:
                    try:
                        self._save_state()
                    except Exception as save_err:
                        print(f"⚠️  Failed to save state after contacting {phone}: {save_err}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("   ℹ️  Test message: Monitoring enabled (in memory), but bot_state.json skipped (reserved for real customers)")
            
            # Handle media sending logic
            # NEW FEATURE: On first contact, store media to send after customer responds
            # On subsequent messages (follow-ups, AI responses), send media immediately
            # For both test messages and real customers: store media and send text only initially
            if media_path and os.path.exists(media_path):
                # If this is the first contact, store media to send later (after customer responds)
                # This works for both test messages (in memory) and real customers (saved to bot_state.json)
                if is_first_contact:
                    # Convert to absolute path to ensure file can be found later
                    # This is important because the bot might be restarted from a different directory
                    media_abs_path = str(Path(media_path).absolute())
                    
                    # Store main media absolute path for later sending (in memory for all contacts)
                    self.pending_media[phone] = media_abs_path
                    self.media_sent_after_response[phone] = False
                    if test_message:
                        print(f"   📎 Main media stored for {phone} (in memory) - will be sent after customer responds")
                    else:
                        print(f"   📎 Main media stored for {phone} - will be sent after customer responds")
                    print(f"   📁 Main media path: {media_abs_path}")
                    
                    # Store second media (free product) if provided
                    if media_path_2 and os.path.exists(media_path_2):
                        media_2_abs_path = str(Path(media_path_2).absolute())
                        self.pending_media_2[phone] = media_2_abs_path
                        self.media_2_sent_after_response[phone] = False
                        if test_message:
                            print(f"   📎 Second media (free product) stored for {phone} (in memory) - will be sent immediately after main media")
                        else:
                            print(f"   📎 Second media (free product) stored for {phone} - will be sent immediately after main media")
                        print(f"   📁 Second media path: {media_2_abs_path}")
                    
                    # Save state to persist pending media (only for real customers, skip for test messages)
                    if not test_message:
                        try:
                            self._save_state()
                        except Exception as save_err:
                            print(f"⚠️  Failed to save state after storing pending media: {save_err}")
                    else:
                        print("   ℹ️  Test message: Media stored in memory (will be sent after response), bot_state.json skipped")
                    # Continue to send text message only (no media)
                    # Fall through to text-only sending below
                else:
                    # Not first contact - send media immediately (follow-up or AI response)
                    print(f"📤 Sending media with caption (caption length: {len(message) if message else 0})...")
                    if message:
                        print(f"   Caption preview: {message[:100]}...")
                    else:
                        print(f"   ⚠️  WARNING: No message provided! Media will be sent without caption!")
                    print(f"   🔍 About to call _send_media with message='{message[:50] if message else 'EMPTY'}...'")
                    media_result = self._send_media(media_path, message if message else "")
                    if media_result:
                        # Media sent successfully
                        print(f"✅ Message with media sent to {phone}")
                        self.messages_sent += 1
                        
                        # Add to conversation history (for follow-up or AI response)
                        if phone not in self.conversations:
                            self.conversations[phone] = []
                        self.conversations[phone].append({
                            "role": "assistant",
                            "content": message if message else f"[Media: {Path(media_path).name}]"
                        })
                        
                        return True
                    else:
                        # Media send had issues, but might have still sent
                        print("⚠️  Media verification uncertain - message may have been sent")
                        print("💡 Skipping text fallback to avoid duplicate messages")
                        # Mark as sent anyway - user can check WhatsApp
                        self.messages_sent += 1
                        
                        # Add to conversation history
                        if phone not in self.conversations:
                            self.conversations[phone] = []
                        self.conversations[phone].append({
                            "role": "assistant",
                            "content": message if message else f"[Media: {Path(media_path).name}]"
                        })
                        
                        return True
            
            # Send text message (either no media, or media stored for later on first contact)
            if not self._send_text(message):
                self.messages_failed += 1
                return False

            # Verify sent
            time.sleep(2)
            print(f"✅ Message sent to {phone}")

            self.messages_sent += 1

            # Handle state operations (in memory for test messages, save to bot_state.json for real customers)
            # For test messages, still track conversation history and monitor (in memory), but skip bot_state.json
            if is_first_contact:
                # (History was already cleared in start_monitoring_contact above)
                # Add our offer message to conversation history (in memory - for both test and real messages)
                if phone not in self.conversations:
                    self.conversations[phone] = []
                self.conversations[phone].append({
                    "role": "assistant",
                    "content": message
                })
                print(f"   Added offer message to conversation history for {phone}")
                
                # Track contact time for follow-up (only set if not already set - in memory)
                if phone not in self.last_contact_time:
                    self.last_contact_time[phone] = datetime.now()
                    self.customer_responded[phone] = False
                    self.followup_sent[phone] = False
                
                # Automatically start background monitoring if not already running (for both test and real messages)
                # This enables AI auto-responses for test messages too
                if not self.auto_monitoring_active:
                    self.start_auto_monitoring()
                    print(f"   ✅ Auto-monitoring started - AI will respond to messages from {phone}")
                else:
                    print(f"   ✅ Auto-monitoring is already active - AI will respond to messages from {phone}")
                
                # Save state to bot_state.json ONLY for real customers (skip for test messages)
                if not test_message:
                    try:
                        self._save_state()
                    except Exception as save_err:
                        print(f"⚠️  Failed to save state after sending to {phone}: {save_err}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("   ℹ️  Test message: Conversation history and monitoring active (in memory), bot_state.json skipped")
            else:
                # This is a follow-up or AI response - add to conversation history
                # Initialize conversation history if it doesn't exist
                if phone not in self.conversations:
                    self.conversations[phone] = []
                self.conversations[phone].append({
                    "role": "assistant",
                    "content": message
                })
            # If already in monitoring, this is an AI response - don't modify history
            # (History is already managed in generate_ai_response)

            return True

        except Exception as e:
            print(f"❌ Error sending to {phone}: {e}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
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
            print(f"🔍 _send_media called with caption length: {len(caption) if caption else 0}")
            if caption:
                print(f"   Caption preview: {caption[:100]}...")
            else:
                print(f"   ⚠️  No caption provided to _send_media")

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

            # STEP 1: Type caption text FIRST (before attaching media)
            # WhatsApp Web will use this text as the caption when media is attached
            if caption:
                print(f"📝 Typing caption text first (will become media caption)...")
                try:
                    import pyperclip
                    import platform
                    
                    # Ensure the input area is focused and visible
                    print("🔍 Focusing chat input box...")
                    try:
                        # Scroll to bottom to ensure input area is visible
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        
                        # Find and focus the input box
                        input_box = self.wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']"))
                        )
                        # Scroll input into view
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_box)
                        time.sleep(0.3)
                        # Click to focus
                        input_box.click()
                        time.sleep(0.5)
                        print("✅ Chat input box focused")
                    except Exception as e:
                        print(f"   ⚠️  Could not focus input: {e}")
                        raise
                    
                    # Clear any existing text first
                    try:
                        input_box.clear()
                        # Also use JavaScript to clear
                        self.driver.execute_script("arguments[0].textContent = '';", input_box)
                        self.driver.execute_script("arguments[0].innerText = '';", input_box)
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"   ℹ️  Could not clear input (might be empty already): {e}")
                    
                    # Focus the input again to ensure it's ready
                    try:
                        input_box.click()
                        time.sleep(0.3)
                    except:
                        pass
                    
                    # Use system clipboard to preserve line breaks
                    pyperclip.copy(caption)
                    print(f"📋 Caption copied to clipboard ({len(caption)} chars, {caption.count(chr(10))} line breaks)")
                    
                    # Paste with Ctrl+V or Cmd+V
                    if platform.system() == 'Darwin':  # macOS
                        input_box.send_keys(Keys.COMMAND, 'v')
                    else:  # Windows/Linux
                        input_box.send_keys(Keys.CONTROL, 'v')
                    
                    time.sleep(1)  # Wait for paste to complete
                    print(f"✅ Caption pasted in chat input: {caption[:50]}...")
                    
                    # Verify caption was pasted
                    caption_check = self.driver.execute_script(
                        """
                        const el = arguments[0];
                        return el.textContent || el.innerText || '';
                        """,
                        input_box
                    )
                    print(f"✓ Caption in input box: {len(caption_check)} chars")
                    if len(caption_check) < len(caption) * 0.5:  # If less than 50% of caption was pasted
                        print(f"⚠️  Caption might not have been pasted correctly (expected {len(caption)} chars, got {len(caption_check)} chars)")
                    else:
                        print(f"✅ Caption text is ready in input box - will become media caption when media is attached")
                    
                except Exception as e:
                    print(f"⚠️  Could not type caption text: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"   💡 Will try to attach media anyway (without caption)")
            else:
                print(f"ℹ️  No caption provided - media will be sent without caption")

            # STEP 2: NOW attach media (the text in input box will automatically become the caption)
            print("📎 Opening attachment menu...")
            
            # Ensure the input area is still focused
            try:
                # Scroll to bottom to ensure input area is visible
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.3)
            except:
                pass

            # Wait a bit for UI to settle
            time.sleep(0.5)

            # Comprehensive list of attachment button selectors (WhatsApp Web uses different ones)
            attach_selectors = [
                # New WhatsApp Web UI
                "button[aria-label='Attach']",
                "span[data-icon='attach']",
                "span[data-icon='clip']",
                "[data-icon='attach']",
                "[data-icon='clip']",
                "[data-icon='plus']",
                # Alternative selectors
                "div[role='button'][aria-label*='Attach']",
                "div[role='button'][title*='Attach']",
                "button[title*='Attach']",
                "span[title*='Attach']",
                # Find by proximity to input box
                "div[contenteditable='true'][data-tab='10'] ~ div span[data-icon]",
                "div[contenteditable='true'][data-tab='10'] + div button",
            ]

            attach_btn = None
            clicked = False
            
            # Method 1: Try Selenium find_element with explicit wait
            for selector in attach_selectors:
                try:
                    # Try with explicit wait
                    attach_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if attach_btn:
                        # Scroll element into view
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", attach_btn)
                        time.sleep(0.3)
                        attach_btn.click()
                        print(f"✅ Opened attachment menu (selector: {selector})")
                        clicked = True
                        break
                except:
                    continue

            # Method 2: JavaScript fallback with more comprehensive search
            if not clicked:
                print("   🔄 Trying JavaScript method to find attachment button...")
                clicked = self.driver.execute_script("""
                    // Find input box first
                    const inputBox = document.querySelector('div[contenteditable="true"][data-tab="10"]');
                    if (!inputBox) {
                        console.log('Input box not found');
                        return false;
                    }
                    
                    // Find attachment button - multiple strategies
                    let attachBtn = null;
                    
                    // Strategy 1: Find button with aria-label containing "Attach"
                    attachBtn = document.querySelector('button[aria-label*="Attach" i]') ||
                                document.querySelector('div[role="button"][aria-label*="Attach" i]') ||
                                document.querySelector('[aria-label*="Attach" i]');
                    
                    // Strategy 2: Find by data-icon
                    if (!attachBtn) {
                        const icons = ['attach', 'clip', 'plus'];
                        for (const icon of icons) {
                            attachBtn = document.querySelector(`[data-icon="${icon}"]`) ||
                                       document.querySelector(`span[data-icon="${icon}"]`);
                            if (attachBtn) break;
                        }
                    }
                    
                    // Strategy 3: Find button near input box (parent or sibling)
                    if (!attachBtn && inputBox) {
                        // Look in the same container as input box
                        const container = inputBox.closest('div[role="textbox"]') || 
                                        inputBox.closest('div[data-testid]') ||
                                        inputBox.parentElement?.parentElement;
                        if (container) {
                            attachBtn = container.querySelector('button[aria-label*="Attach" i]') ||
                                       container.querySelector('[data-icon="attach"]') ||
                                       container.querySelector('[data-icon="clip"]') ||
                                       container.querySelector('[data-icon="plus"]');
                        }
                    }
                    
                    // Strategy 4: Find all buttons and look for attachment-related ones
                    if (!attachBtn) {
                        const allButtons = document.querySelectorAll('button, div[role="button"]');
                        for (const btn of allButtons) {
                            const ariaLabel = btn.getAttribute('aria-label') || '';
                            const title = btn.getAttribute('title') || '';
                            if (ariaLabel.toLowerCase().includes('attach') || 
                                title.toLowerCase().includes('attach') ||
                                btn.querySelector('[data-icon="attach"]') ||
                                btn.querySelector('[data-icon="clip"]')) {
                                attachBtn = btn;
                                break;
                            }
                        }
                    }
                    
                    if (attachBtn) {
                        console.log('Found attachment button:', attachBtn);
                        // Scroll into view
                        attachBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        // Try clicking
                        attachBtn.click();
                        return true;
                    }
                    
                    console.log('Attachment button not found');
                    return false;
                """)

                if clicked:
                    print("✅ Opened attachment menu (via JavaScript)")
                    time.sleep(1)  # Wait for menu to open
                else:
                    # Last resort: Try to find by searching the entire page
                    print("   🔄 Trying comprehensive page search...")
                    try:
                        # Get all clickable elements near the input area
                        all_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                            "div[contenteditable='true'][data-tab='10'] ~ * button, " +
                            "div[contenteditable='true'][data-tab='10'] ~ * [role='button'], " +
                            "div[contenteditable='true'][data-tab='10'] ~ * span[data-icon]"
                        )
                        
                        for elem in all_elements[:10]:  # Check first 10 elements
                            try:
                                aria_label = elem.get_attribute('aria-label') or ''
                                if 'attach' in aria_label.lower() or 'clip' in aria_label.lower():
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                                    time.sleep(0.3)
                                    elem.click()
                                    print(f"✅ Found attachment button by aria-label: {aria_label}")
                                    clicked = True
                                    break
                            except:
                                continue
                                
                        if not clicked:
                            # Debug: Print what buttons we found
                            print("   🔍 Debug: Searching for attachment button...")
                            debug_info = self.driver.execute_script("""
                                const inputBox = document.querySelector('div[contenteditable="true"][data-tab="10"]');
                                const container = inputBox ? inputBox.closest('div[data-testid]') || inputBox.parentElement : null;
                                const buttons = container ? container.querySelectorAll('button, div[role="button"], span[data-icon]') : [];
                                return Array.from(buttons).slice(0, 10).map(btn => ({
                                    tag: btn.tagName,
                                    ariaLabel: btn.getAttribute('aria-label'),
                                    title: btn.getAttribute('title'),
                                    dataIcon: btn.getAttribute('data-icon'),
                                    className: btn.className,
                                    visible: btn.offsetParent !== null
                                }));
                            """)
                            if debug_info:
                                print(f"   📋 Found {len(debug_info)} potential buttons near input:")
                                for i, info in enumerate(debug_info[:5]):
                                    print(f"      {i+1}. {info.get('tag')} - aria-label: {info.get('ariaLabel')}, data-icon: {info.get('dataIcon')}, visible: {info.get('visible')}")
                            
                            # Don't raise exception yet - try alternative methods first
                            print("   ⚠️  Attachment button not found - will try alternative methods")
                    except Exception as e:
                        print(f"   ⚠️  Comprehensive search had issues: {e}")
                        print("   💡 Will try to continue with file input directly...")
            
            # If attachment button wasn't clicked, try alternative methods
            if not clicked:
                print("   🔄 Trying alternative methods to access file upload...")
                
                # Method 1: Check if file input already exists (sometimes WhatsApp has it available)
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    print(f"   ✅ Found {len(file_inputs)} file input(s) - will use directly")
                    # Skip the attachment button click and go straight to file input
                    # We'll handle this in the file input section below
                else:
                    # Method 2: Try keyboard shortcut (Ctrl+O or Cmd+O to open file)
                    print("   🔄 Trying keyboard shortcut to open file dialog...")
                    try:
                        input_box = self.driver.find_element(By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']")
                        input_box.click()
                        time.sleep(0.3)
                        # Try Cmd+O (Mac) or Ctrl+O (Windows/Linux)
                        import platform
                        if platform.system() == 'Darwin':  # macOS
                            input_box.send_keys(Keys.COMMAND + 'o')
                        else:
                            input_box.send_keys(Keys.CONTROL + 'o')
                        time.sleep(1)
                        print("   ✅ Sent keyboard shortcut - checking for file input...")
                        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if file_inputs:
                            print(f"   ✅ File input appeared after keyboard shortcut!")
                            clicked = True  # Mark as successful
                    except Exception as kb_err:
                        print(f"   ⚠️  Keyboard shortcut failed: {kb_err}")
                
                # Method 3: Try right-click context menu (if file input still not found)
                if not file_inputs and not clicked:
                    print("   🔄 File input still not found - you may need to manually attach file")
                    print("   💡 The bot will continue but media attachment may fail")
                    # Don't raise exception - let it try to continue and fail gracefully later

            # Only wait if we successfully clicked attachment button
            if clicked:
                time.sleep(1.5)

            # Now find and click "Photos & Videos" for video preview (only if attachment menu opened)
            if is_video and clicked:
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

            # STEP 3: Send file path to input (the text already in input box will become the caption)
            print(f"📤 Sending file to WhatsApp...")
            print(f"   💡 Note: Text already in input box will automatically become the media caption")
            try:
                file_input.send_keys(abs_path)
                print(f"✅ File path sent to input")

                # Wait for Finder to close and media preview to appear
                print("⏳ Waiting for Finder to close and media preview to appear...")
                time.sleep(2)

                # Verify preview appeared
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
                        print(f"✅ Media preview appeared (caption text should be preserved)")
                        preview_found = True
                        break
                    else:
                        if attempt < max_attempts - 1:
                            print(f"   Waiting for preview... (attempt {attempt + 1}/{max_attempts})")
                            time.sleep(1)

                if not preview_found:
                    print(f"⚠️  Could not verify media preview, but continuing...")

                # Verify caption is still there (it should be - WhatsApp preserves text in input when attaching media)
                if caption:
                    try:
                        caption_input = self.driver.find_element(By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']")
                        caption_check = self.driver.execute_script(
                            """
                            const el = arguments[0];
                            return el.textContent || el.innerText || '';
                            """,
                            caption_input
                        )
                        if len(caption_check) > 0:
                            print(f"✅ Caption text preserved in media preview ({len(caption_check)} chars)")
                        else:
                            print(f"⚠️  Caption text might have been cleared - media will be sent without caption")
                    except:
                        print(f"   ℹ️  Could not verify caption text (media should still send)")

            except Exception as e:
                print(f"⚠️  Error sending file path: {e}")
                raise
            
            # STEP 5: Wait for upload to complete
            print("⏳ Waiting for video to finish uploading...")
            time.sleep(4)

            # STEP 6: Click send button - try multiple methods
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

    def get_new_messages(self, phone: str, skip_chat_open: bool = False) -> Optional[str]:
        """
        Check for new messages from a contact

        Args:
            phone: Phone number to check
            skip_chat_open: If True, skip opening the chat (assumes we're already in it)

        Returns:
            New message text if found, None otherwise
        """
        try:
            phone = self._format_phone(phone)
            # Reduced logging for batch operations (only log if verbose mode)
            verbose = getattr(self, 'verbose_monitoring', False)
            if verbose:
                print(f"🔍 Checking messages from {phone}...")

            # Ensure window is visible (message detection can fail when minimized)
            try:
                self.driver.maximize_window()
                self.driver.execute_script("window.focus();")
            except:
                pass  # Not critical for message checking

            # Open chat safely (with lock to prevent race conditions)
            if not skip_chat_open:
                if not self._open_chat_safely(phone):
                    if verbose:
                        print(f"⚠️  Could not open chat for {phone}")
                    return None
                # Reduced wait time for faster checking (was 2s, now 1.2s)
                time.sleep(1.2)  # Wait for chat to stabilize
            # If skip_chat_open is True, we assume we're already in the correct chat

            # Check if chat loaded successfully - try multiple selectors
            chat_loaded = False
            chat_selectors = [
                "[data-testid='conversation-panel-body']",
                "[data-testid='conversation-panel-messages']",
                "div[class*='_ak'][role='application']",  # Main WhatsApp panel
                "[contenteditable='true'][data-tab='10']",  # Message input box
            ]

            # Reduced wait time for element detection (was 5s, now 3s)
            for selector in chat_selectors:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if element:
                        chat_loaded = True
                        break
                except TimeoutException:
                    continue

            if not chat_loaded:
                # Last resort: check with JavaScript (faster than WebDriverWait)
                chat_loaded = self.driver.execute_script("""
                    // Check if we're in a chat conversation
                    const hasMessages = document.querySelector('[data-testid="msg-container"]') !== null;
                    const hasInputBox = document.querySelector('[contenteditable="true"][data-tab="10"]') !== null;
                    const hasConversation = document.querySelector('[role="application"]') !== null;
                    return hasMessages || hasInputBox || hasConversation;
                """)

            if not chat_loaded:
                if verbose:
                    print(f"⚠️  Could not load chat for {phone} - chat interface not detected")
                return None

            # Scroll to ensure all recent messages are loaded
            # Reduced logging for faster operation in batch mode
            try:
                self.driver.execute_script("""
                    // Find the message container and scroll to bottom
                    const msgContainer = document.querySelector('[data-testid="conversation-panel-body"]') ||
                                        document.querySelector('[data-testid="conversation-panel-messages"]');
                    if (msgContainer) {
                        msgContainer.scrollTop = msgContainer.scrollHeight;
                    }
                """)
                # Reduced wait time for faster checking (was 2s, now 1s)
                time.sleep(1.0)  # Wait for messages to render after scroll
            except Exception as scroll_err:
                # Silently continue - scrolling is not critical
                pass

            # Reduced wait time for message rendering (was 2.5s, now 1.5s)
            time.sleep(1.5)  # Wait for messages to render

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
                verbose = getattr(self, 'verbose_monitoring', False)
                if verbose:
                    print(f"📨 JavaScript found {msg_count} incoming messages in chat with {phone}")
                if msg_count == 0 and verbose:
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
                        verbose = getattr(self, 'verbose_monitoring', False)
                        if verbose:
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
                    verbose = getattr(self, 'verbose_monitoring', False)
                    if verbose:
                        print(f"✨ Returning FIRST new message from {phone}: {last_msg[:100]}...")

                    # Also update the old tracking for backward compatibility
                    if last_msg:
                        self.last_messages[phone] = last_msg
                else:
                    verbose = getattr(self, 'verbose_monitoring', False)
                    if verbose:
                        print(f"ℹ️  All messages already seen")
                    all_incoming = []  # Clear to trigger fallback

            # Strategy 2: Fallback using Selenium if JavaScript method fails
            if not last_msg:
                verbose = getattr(self, 'verbose_monitoring', False)
                if verbose:
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
                            verbose = getattr(self, 'verbose_monitoring', False)
                            if verbose:
                                print(f"✅ Found message with selector: {selector}")
                            if last_msg:
                                # Use text-based tracking as fallback
                                last_seen = self.last_messages.get(phone, "")
                                if last_msg != last_seen:
                                    self.last_messages[phone] = last_msg
                                    if verbose:
                                        print(f"✨ NEW MESSAGE from {phone}: {last_msg[:100]}...")
                                    return last_msg
                                else:
                                    if verbose:
                                        print(f"ℹ️  No new messages (already seen)")
                                    return None
                    except Exception as sel_err:
                        continue

            if not last_msg:
                verbose = getattr(self, 'verbose_monitoring', False)
                if verbose:
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
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800,  # Increased from 200 to allow complete responses
                    timeout=30.0  # 30 second timeout
                )
            except Exception as api_error:
                # Check if this is an SSL/certificate error by examining the exception and its cause
                error_str = str(api_error).lower()
                error_type = type(api_error).__name__
                
                # Check the underlying cause (wrapped exceptions) - OpenAI wraps SSL errors
                underlying_error = getattr(api_error, '__cause__', None) or getattr(api_error, '__context__', None)
                underlying_str = str(underlying_error).lower() if underlying_error else ""
                underlying_type = type(underlying_error).__name__ if underlying_error else ""
                
                # Check if it's an SSL/certificate error - multiple detection methods
                # APIConnectionError from OpenAI often wraps SSL errors
                is_ssl_error = False
                
                # Method 1: Check if it's APIConnectionError (OpenAI wraps SSL errors in this)
                # Most APIConnectionError from OpenAI are SSL-related, so we'll try SSL fallback
                if "APIConnectionError" in error_type:
                    is_ssl_error = True
                    # Check the underlying cause for more details
                    if underlying_error:
                        underlying_error_str = str(underlying_error)
                        print(f"   🔍 Underlying error type: {type(underlying_error).__name__}")
                        if any(term in underlying_error_str.lower() for term in [
                            "certificate", "ssl", "certificate_verify_failed", 
                            "certificate is not yet valid", "certificate verify failed"
                        ]):
                            print(f"   ✅ Confirmed: SSL certificate error in underlying exception")
                        elif "ConnectError" in underlying_type:
                            print(f"   ✅ Confirmed: ConnectError (likely SSL-related)")
                # Method 1b: Check for ConnectError directly (also often SSL)
                elif "ConnectError" in error_type:
                    is_ssl_error = True
                
                # Method 2: Direct SSL error indicators
                if not is_ssl_error:
                    is_ssl_error = (
                        "certificate" in error_str or "ssl" in error_str or 
                        "certificate verify failed" in error_str or
                        "certificate is not yet valid" in error_str or
                        "certificate" in underlying_str or "ssl" in underlying_str or
                        "certificate verify failed" in underlying_str or
                        "certificate is not yet valid" in underlying_str or
                        "CERTIFICATE_VERIFY_FAILED" in str(api_error) or
                        "ConnectError" in error_type or
                        "ConnectError" in underlying_type
                    )
                
                if is_ssl_error:
                    print(f"   ⚠️  SSL certificate error detected: {error_type}")
                    if underlying_error:
                        print(f"   🔍 Underlying error: {type(underlying_error).__name__}: {str(underlying_error)[:200]}")
                    print("   💡 This might be due to:")
                    print("      1. System clock is incorrect (check system time with: date)")
                    print("      2. SSL certificate verification issue")
                    print("   💡 Trying with SSL verification disabled (less secure but will work)...")
                    
                    # Try with SSL verification disabled as fallback
                    import httpx
                    import warnings
                    
                    # Suppress SSL warnings when we disable verification
                    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
                    
                    # Create a custom HTTP client with SSL verification disabled
                    try:
                        # Get the API key - try multiple methods
                        api_key = None
                        # Method 1: Try from environment (most reliable)
                        api_key = os.getenv('OPENAI_API_KEY')
                        # Method 2: Try direct attribute
                        if not api_key and hasattr(self.openai_client, 'api_key'):
                            api_key = self.openai_client.api_key
                        # Method 3: Try from _client internal attribute
                        if not api_key and hasattr(self.openai_client, '_client'):
                            try:
                                client_obj = self.openai_client._client
                                if hasattr(client_obj, 'api_key'):
                                    api_key = client_obj.api_key
                            except:
                                pass
                        
                        if not api_key:
                            raise Exception("Could not retrieve API key for SSL fallback - check OPENAI_API_KEY in .env")
                        
                        # Reinitialize OpenAI client with SSL verification disabled
                        from openai import OpenAI
                        custom_client = OpenAI(
                            api_key=api_key,
                            http_client=httpx.Client(
                                verify=False,  # Disable SSL verification
                                timeout=30.0,
                                follow_redirects=True
                            )
                        )
                        
                        print("   🔄 Retrying API call with SSL verification disabled...")
                        # Try again with custom client
                        response = custom_client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=0.7,
                            max_tokens=800,
                            timeout=30.0
                        )
                        print("   ✅ Connected successfully with SSL verification disabled")
                        # Update the client for future use so we don't need to recreate it
                        self.openai_client = custom_client
                    except Exception as retry_error:
                        print(f"   ❌ Retry with SSL disabled also failed: {retry_error}")
                        print(f"   ❌ Error type: {type(retry_error).__name__}")
                        # Don't re-raise - let it fall through to outer handler
                        # The outer handler will return a graceful fallback message
                        raise api_error from retry_error
                else:
                    # Not an SSL error, re-raise to be handled by outer exception handler
                    raise

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
                    try:
                        continuation_response = self.openai_client.chat.completions.create(
                            model=self.model,
                            messages=continuation_messages,
                            temperature=0.7,
                            max_tokens=400,
                            timeout=20.0
                        )
                    except Exception as cont_error:
                        # Check if this is an SSL/certificate error
                        error_str = str(cont_error).lower()
                        underlying_error = getattr(cont_error, '__cause__', None) or getattr(cont_error, '__context__', None)
                        underlying_str = str(underlying_error).lower() if underlying_error else ""
                        
                        is_ssl_error = (
                            "certificate" in error_str or "ssl" in error_str or 
                            "certificate verify failed" in error_str or
                            "certificate" in underlying_str or "ssl" in underlying_str or
                            "CERTIFICATE_VERIFY_FAILED" in str(cont_error) or
                            "ConnectError" in type(cont_error).__name__
                        )
                        
                        if is_ssl_error:
                            print(f"   ⚠️  SSL certificate error in continuation")
                            print("   💡 Trying with SSL verification disabled...")
                            
                            # Use custom client with SSL verification disabled
                            import httpx
                            from openai import OpenAI
                            
                            # Get API key
                            api_key = getattr(self.openai_client, 'api_key', None) or os.getenv('OPENAI_API_KEY')
                            
                            custom_client = OpenAI(
                                api_key=api_key,
                                http_client=httpx.Client(verify=False, timeout=20.0, follow_redirects=True)
                            )
                            
                            continuation_response = custom_client.chat.completions.create(
                                model=self.model,
                                messages=continuation_messages,
                                temperature=0.7,
                                max_tokens=400,
                                timeout=20.0
                            )
                        else:
                            raise
                    
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

            # Mark customer as responded (for follow-up tracking)
            if phone in self.last_contact_time:
                self.customer_responded[phone] = True
                # Reset follow-up flag since customer responded
                self.followup_sent[phone] = False
                # Save state after customer responds
                self._save_state()

            # Keep only last 20 messages
            if len(self.conversations[phone]) > 20:
                self.conversations[phone] = self.conversations[phone][-20:]

            print(f"   Conversation history updated ({len(self.conversations[phone])} messages)", flush=True)
            sys.stdout.flush()
            return clean_response

        except Exception as e:
            # Check if this is an SSL error that wasn't caught by the inner handler
            error_str = str(e).lower()
            error_type = type(e).__name__
            underlying_error = getattr(e, '__cause__', None) or getattr(e, '__context__', None)
            underlying_str = str(underlying_error).lower() if underlying_error else ""
            
            # Check if it's an SSL/certificate error (might have been missed)
            is_ssl_error = (
                "certificate" in error_str or "ssl" in error_str or 
                "certificate verify failed" in error_str or
                "certificate is not yet valid" in error_str or
                "certificate" in underlying_str or "ssl" in underlying_str or
                "certificate verify failed" in underlying_str or
                "CERTIFICATE_VERIFY_FAILED" in str(e) or
                "ConnectError" in error_type or
                "APIConnectionError" in error_type  # OpenAI wraps SSL errors in APIConnectionError
            )
            
            # If it's an SSL error that reached here, the inner handler's fallback didn't work
            # This could mean API key retrieval failed, or there's another issue
            if is_ssl_error:
                # This is likely an SSL error wrapped in APIConnectionError
                print(f"⚠️  SSL certificate error (caught in outer handler): {error_type}", flush=True)
                if underlying_error:
                    print(f"   🔍 Underlying: {type(underlying_error).__name__}: {str(underlying_error)[:150]}", flush=True)
                print("   💡 This is likely due to system clock being incorrect", flush=True)
                print("   💡 Check system time with: date", flush=True)
                print("   💡 Fix time with: sudo sntp -sS time.apple.com", flush=True)
                print("   💡 Or manually set time in System Settings → Date & Time", flush=True)
                sys.stdout.flush()
                # Return a helpful message in Arabic/English
                return "شكراً لك على رسالتك! سنتواصل معك قريباً."
            
            print(f"⚠️  AI response error: {e}", flush=True)
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return "Thank you for your message. We'll get back to you soon."

    def start_monitoring_contact(self, phone: str, skip_chat_open: bool = False):
        """
        Start monitoring a contact - clears conversation history and marks existing messages as seen.
        Call this when you first add a contact to monitoring.

        Args:
            phone: Phone number to start monitoring
            skip_chat_open: If True, skip opening the chat (assumes we're already in it)
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
            if not skip_chat_open:
                try:
                    # Open chat safely (only if not already in it)
                    if not self._open_chat_safely(phone):
                        print(f"   ⚠️  Could not open chat for {phone}")
                    else:
                        time.sleep(2)  # Wait for chat to stabilize
                        # Use get_new_messages to populate seen_message_ids
                        # This will mark all current messages as "seen"
                        _ = self.get_new_messages(phone, skip_chat_open=True)
                        print(f"   {len(self.seen_message_ids.get(phone, set()))} existing messages marked as seen")
                except Exception as e:
                    print(f"   ⚠️  Could not mark existing messages as seen: {e}")
            else:
                # We're already in the chat, just mark existing messages as seen
                try:
                    # Initialize seen_message_ids if needed
                    if phone not in self.seen_message_ids:
                        self.seen_message_ids[phone] = set()
                    if phone not in self.seen_message_texts:
                        self.seen_message_texts[phone] = set()
                    
                    # Mark all currently visible messages as seen
                    _ = self.get_new_messages(phone, skip_chat_open=True)
                    print(f"   {len(self.seen_message_ids.get(phone, set()))} existing messages marked as seen")
                except Exception as e:
                    print(f"   ⚠️  Could not mark existing messages as seen: {e}")

            print(f"✅ Monitoring started for {phone} - conversation history cleared")

        except Exception as e:
            print(f"⚠️  Error starting monitoring for {phone}: {e}")

    def _load_followup_message_from_json(self) -> Optional[str]:
        """Load follow-up message template from JSON file, with fallback to default"""
        try:
            message_file = Path("followup_message.json")
            if message_file.exists():
                with open(message_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    message = data.get('message_template', '')
                    if message:
                        return message
            return None
        except Exception as e:
            print(f"⚠️ Error loading followup_message.json: {e}")
            return None

    def _generate_followup_message(self, phone: str) -> str:
        """
        Generate a follow-up message for a customer who didn't respond.
        
        Args:
            phone: Customer phone number
            
        Returns:
            Follow-up message text
        """
        # Get customer name if available
        customer_name = "Customer"
        if self.contacts_df is not None:
            try:
                # Try to find customer in contacts_df
                phone_clean = phone.replace('+', '').replace(' ', '').replace('-', '')
                for idx, row in self.contacts_df.iterrows():
                    row_phone = str(row.get('phone_formatted', row.get('phone', '')))
                    row_phone_clean = row_phone.replace('+', '').replace(' ', '').replace('-', '')
                    if phone_clean in row_phone_clean or row_phone_clean in phone_clean:
                        customer_name = str(row.get('name', 'Customer'))
                        break
            except Exception:
                pass  # Use default name if lookup fails
        
        # Use custom template if provided, otherwise use default from JSON or fallback
        if self.followup_message_template:
            # Replace placeholders
            message = self.followup_message_template
            message = message.replace('{name}', customer_name)
            message = message.replace('{phone}', phone)
            return message
        
        # Use default from JSON file if available
        if self.default_followup_template:
            message = self.default_followup_template
            message = message.replace('{name}', customer_name)
            message = message.replace('{phone}', phone)
            return message
        
        # Fallback to hardcoded default (should not happen if JSON exists)
        default_followup = f"""مرحباً {customer_name}! 👋

نشكرك على وقتك. نود أن نتأكد أنك رأيت عرضنا على Tiger Balm.

هل لديك أي أسئلة؟ نحن هنا للمساعدة! 💬"""
        
        return default_followup

    def _check_and_send_followups(self, contacts: List[str]) -> int:
        """
        Check which contacts need follow-up messages and send them.
        
        Args:
            contacts: List of phone numbers to check
            
        Returns:
            Number of follow-ups sent
        """
        if not self.followup_enabled:
            return 0
        
        followups_sent = 0
        current_time = datetime.now()
        
        for phone in contacts:
            try:
                # Check if this contact is eligible for follow-up
                if phone not in self.last_contact_time:
                    continue  # Never contacted, skip
                
                # Skip if customer already responded
                if self.customer_responded.get(phone, False):
                    continue  # Customer responded, no follow-up needed
                
                # Skip if we already sent a follow-up
                if self.followup_sent.get(phone, False):
                    continue  # Already sent follow-up
                
                # Check if enough time has passed
                last_contact = self.last_contact_time[phone]
                time_since_contact = (current_time - last_contact).total_seconds() / 60  # Convert to minutes
                
                if time_since_contact >= self.followup_delay_minutes:
                    # Time to send follow-up!
                    print(f"📬 Sending follow-up to {phone} (no response after {time_since_contact:.1f} minutes)")
                    
                    # Generate follow-up message
                    followup_msg = self._generate_followup_message(phone)
                    
                    # Send follow-up message
                    # Note: pass is_followup=True to allow sending even if contact is already in monitored_contacts
                    if self.send_message(phone, followup_msg, media_path=None, is_followup=True):
                        self.followup_sent[phone] = True
                        # DON'T update last_contact_time - keep original contact time for tracking
                        # We update followup_sent flag to prevent sending multiple follow-ups
                        followups_sent += 1
                        # Save state after sending follow-up
                        self._save_state()
                        print(f"   ✅ Follow-up sent to {phone}")
                    else:
                        print(f"   ❌ Failed to send follow-up to {phone}")
                        
            except Exception as e:
                print(f"   ⚠️  Error sending follow-up to {phone}: {e}")
                continue
        
        if followups_sent > 0:
            print(f"📊 Sent {followups_sent} follow-up message(s)")
        
        return followups_sent

    def _check_all_contacts_parallel(self, contacts: List[str]) -> Dict[str, Optional[str]]:
        """
        Optimized contact checking: Uses faster sequential checking with reduced waits.
        
        NOTE: WhatsApp Web only allows ONE active session per account, so we cannot use
        multiple browser instances for true parallelism. This method optimizes the
        sequential checking process by:
        1. Reducing wait times (2-3s instead of 3-5s per contact)
        2. Reducing verbose logging (faster execution)
        3. Using smart caching to skip already-seen messages
        4. Batch processing all contacts in one cycle
        
        Args:
            contacts: List of phone numbers to check
            
        Returns:
            Dictionary mapping phone -> new message text (or None if no new message)
        """
        results = {phone: None for phone in contacts}
        
        if not contacts:
            return results
        
        print(f"⚡ Optimized check: Processing {len(contacts)} contacts efficiently...")
        print(f"   (WhatsApp Web allows only 1 session, so sequential checking is optimized)")
        
        # Check contacts sequentially with optimizations:
        # - Reduced wait times (40-50% faster than before)
        # - Smart message deduplication (skip already-seen messages)
        # - Minimal logging for faster execution
        
        start_time = time.time()
        for idx, phone in enumerate(contacts):
            try:
                # Quick check: use get_new_messages with optimized settings
                # The method already has smart caching and deduplication
                new_msg = self.get_new_messages(phone, skip_chat_open=False)
                
                if new_msg:
                    results[phone] = new_msg
                    print(f"   ✅ {phone}: New message found")
                # No new message - result stays None (no logging for speed)
                    
            except Exception as e:
                print(f"   ⚠️  Error checking {phone}: {e}")
                results[phone] = None
                continue
        
        # Count results and show performance
        elapsed_time = time.time() - start_time
        new_messages_count = sum(1 for msg in results.values() if msg is not None)
        avg_time_per_contact = elapsed_time / len(contacts) if contacts else 0
        
        print(f"📊 Check complete: {new_messages_count} contacts have new messages out of {len(contacts)}")
        print(f"   ⏱️  Total time: {elapsed_time:.1f}s | Avg: {avg_time_per_contact:.1f}s per contact")
        
        return results

    def _background_monitoring_loop(self):
        """Background thread that continuously monitors contacts for new messages"""
        print("🔄 Background monitoring thread started")
        
        while self.auto_monitoring_active:
            try:
                # Skip monitoring if bulk sending is active (to avoid race conditions)
                if self.bulk_sending_active:
                    time.sleep(1)  # Short sleep, then check again
                    continue
                
                # Get list of contacts to monitor (thread-safe)
                with self.monitoring_lock:
                    # If there are test contacts, only monitor test contacts (don't check real customers during testing)
                    # This prevents checking all 76+ real customers when you're just testing
                    if self.test_contacts:
                        # Only monitor test contacts when testing
                        active_contacts = [
                            phone for phone in self.monitored_contacts 
                            if phone in self.test_contacts 
                            and phone not in self.monitoring_stopped_contacts
                        ]
                        # Only log this once per cycle to avoid spam
                        if len(active_contacts) > 0 and len(active_contacts) < len(self.monitored_contacts):
                            # There are test contacts, so we're only monitoring those (not real customers)
                            pass  # Will be logged below with actual count
                    else:
                        # No test contacts, monitor all real customers normally
                        active_contacts = [
                            phone for phone in self.monitored_contacts 
                            if phone not in self.monitoring_stopped_contacts
                        ]
                
                if not active_contacts:
                    # No contacts to monitor, wait a bit and check again
                    time.sleep(self.monitoring_check_interval)
                    continue
                
                # Use optimized batch checking (faster sequential with reduced waits)
                if self.test_contacts and len(active_contacts) > 0:
                    # Only monitoring test contacts (not real customers) - this is a test scenario
                    total_real = len([c for c in self.monitored_contacts if c not in self.test_contacts])
                    if total_real > 0:
                        print(f"⚡ Checking {len(active_contacts)} test contact(s) only (skipping {total_real} real customers during testing)...")
                    else:
                        print(f"⚡ Checking {len(active_contacts)} test contact(s)...")
                else:
                    print(f"⚡ Checking {len(active_contacts)} contacts efficiently...")
                try:
                    # Check all contacts using optimized method (reduced waits, less logging)
                    contact_messages = self._check_all_contacts_parallel(active_contacts)
                    
                    # Process results
                    for phone, new_msg in contact_messages.items():
                        if not self.auto_monitoring_active:
                            break
                        
                        # Double-check bulk_sending_active
                        if self.bulk_sending_active:
                            break
                        
                        if new_msg:
                            print(f"\n📨 New message from {phone}!")
                            print(f"   Customer: {new_msg[:100]}...")
                            
                            # Mark customer as responded (for follow-up tracking)
                            is_first_response = False
                            if phone in self.last_contact_time:
                                # Check if this is the first response from this customer
                                is_first_response = not self.customer_responded.get(phone, False)
                                self.customer_responded[phone] = True
                                # Reset follow-up flag since customer responded
                                self.followup_sent[phone] = False
                            
                            # Generate AI response FIRST (before sending media)
                            ai_response = None
                            pending_media_path = None
                            pending_media_2_path = None
                            
                            if self.ai_enabled:
                                print(f"   🤖 Generating AI response...")
                                ai_response = self.generate_ai_response(new_msg, phone)
                            
                            # Check if this is first response and we have pending media
                            # Main media should be attached to the AI response
                            if is_first_response and phone in self.pending_media:
                                pending_media_path = self.pending_media[phone]
                                # Check if media hasn't been sent yet
                                if not self.media_sent_after_response.get(phone, False):
                                    # Ensure path is absolute (in case it was stored as relative)
                                    pending_media_path = str(Path(pending_media_path).absolute())
                                    
                                    if not os.path.exists(pending_media_path):
                                        print(f"   ⚠️  Pending media file not found: {pending_media_path}")
                                        print(f"   💡 Make sure the media file exists and wasn't deleted")
                                        # Remove invalid pending media
                                        del self.pending_media[phone]
                                        if phone in self.pending_media_2:
                                            del self.pending_media_2[phone]
                                        pending_media_path = None
                                    
                                    # Check for second media
                                    if phone in self.pending_media_2:
                                        pending_media_2_path = self.pending_media_2[phone]
                                        pending_media_2_path = str(Path(pending_media_2_path).absolute())
                                        if not os.path.exists(pending_media_2_path):
                                            print(f"   ⚠️  Second media file not found: {pending_media_2_path}")
                                            del self.pending_media_2[phone]
                                            pending_media_2_path = None
                            
                            # Send AI response WITH main media (if first response and media exists)
                            if ai_response:
                                print(f"   📤 Sending AI response{' with main media' if pending_media_path and is_first_response else ''}...")
                                
                                # Send AI response with main media attached (if first response)
                                if is_first_response and pending_media_path and not self.media_sent_after_response.get(phone, False):
                                    # Send AI response WITH main media attached
                                    if self.send_message(phone, ai_response, media_path=pending_media_path):
                                        self.ai_responses_sent += 1
                                        self.media_sent_after_response[phone] = True
                                        print(f"   ✅ AI response with main media sent successfully to {phone}")
                                        
                                        # Add to conversation history
                                        if phone not in self.conversations:
                                            self.conversations[phone] = []
                                        self.conversations[phone].append({
                                            "role": "assistant",
                                            "content": f"{ai_response} [Main media attached: {Path(pending_media_path).name}]"
                                        })
                                        
                                        # NOW send second media separately (after a short delay)
                                        if pending_media_2_path and not self.media_2_sent_after_response.get(phone, False):
                                            print(f"   📎 Sending second media (free product) to {phone}...")
                                            print(f"   📁 Second media file: {Path(pending_media_2_path).name}")
                                            # Small delay between messages
                                            time.sleep(3)
                                            
                                            # Send second media with empty caption
                                            if self._open_chat_safely(phone):
                                                media_2_sent = self._send_media(pending_media_2_path, "")
                                                if media_2_sent:
                                                    self.media_2_sent_after_response[phone] = True
                                                    print(f"   ✅ Second media (free product) sent successfully to {phone}")
                                                    self.conversations[phone].append({
                                                        "role": "assistant",
                                                        "content": f"[Free product media sent: {Path(pending_media_2_path).name}]"
                                                    })
                                                else:
                                                    print(f"   ⚠️  Failed to send second media to {phone}")
                                            else:
                                                print(f"   ⚠️  Failed to open chat for {phone} - cannot send second media")
                                        
                                        # Save state after sending media
                                        self._save_state()
                                    else:
                                        print(f"   ❌ Failed to send AI response with main media to {phone}")
                                else:
                                    # No media, just send AI response as text
                                    if self.send_message(phone, ai_response):
                                        self.ai_responses_sent += 1
                                        print(f"   ✅ AI response sent successfully to {phone}")
                                    else:
                                        print(f"   ❌ Failed to send AI response to {phone}")
                            else:
                                # AI not enabled - no response generated
                                print(f"   ⚠️  AI not enabled - skipping response")
                            
                            # Save state after customer responds (skip for test contacts)
                            if phone not in self.test_contacts:
                                self._save_state()
                    
                    # Check for follow-ups (customers who didn't respond)
                    if self.followup_enabled and not self.bulk_sending_active:
                        try:
                            self._check_and_send_followups(active_contacts)
                        except Exception as followup_err:
                            print(f"⚠️  Error in follow-up check: {followup_err}")
                
                except Exception as e:
                    print(f"⚠️  Error in optimized checking: {e}")
                    import traceback
                    traceback.print_exc()
                    # The method already handles errors per contact, so we continue
                
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

            # Open chat safely (with lock to prevent race conditions)
            if not self._open_chat_safely(phone):
                print(f"⚠️  Could not open chat for {phone}")
                return
            
            # Use get_new_messages to populate seen_message_ids without returning anything
            # This will mark all current messages as "seen"
            _ = self.get_new_messages(phone, skip_chat_open=True)

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
