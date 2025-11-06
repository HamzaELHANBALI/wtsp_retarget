from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timedelta
import time
import random
import pandas as pd
import openai
import threading
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class SaudiWhatsAppRetargeterWithAI:
    """
    Enhanced WhatsApp retargeting solution with AI-powered automatic responses.
    Features:
    - Send bulk messages to customers
    - Monitor incoming messages
    - Automatically respond using OpenAI API
    - Maintain conversation context
    """
    
    def __init__(self, daily_limit=40, openai_api_key: Optional[str] = None, system_prompt: Optional[str] = None):
        """
        Initialize the retargeter with AI capabilities
        
        Args:
            daily_limit: Maximum messages per day
            openai_api_key: Your OpenAI API key (or set OPENAI_API_KEY env var)
            system_prompt: Custom system prompt for AI responses
        """
        # Track daily usage
        self.daily_limit = daily_limit
        self.daily_usage = 0
        self.daily_reset_date = datetime.now().date()
        
        # OpenAI setup
        import os
        self.openai_client = None
        
        # Priority: 1. Parameter, 2. Environment variable (from .env file)
        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
            self.ai_enabled = True
            if openai_api_key:
                print("✅ OpenAI API configured from parameter")
            else:
                print("✅ OpenAI API configured from .env file")
        else:
            print("⚠️  Warning: OpenAI API key not set. AI responses will be disabled.")
            print("   Add OPENAI_API_KEY to .env file or pass as parameter")
            self.ai_enabled = False
        
        # System prompt for AI
        self.system_prompt = system_prompt or """You are a helpful customer service representative for a business targeting Saudi Arabia customers.
You communicate in Arabic and English. Be professional, friendly, and helpful.
Always respond in a way that matches the customer's language preference."""
        
        # Conversation history (phone -> list of messages)
        self.conversation_history: Dict[str, List[Dict]] = {}
        
        # Track contacts we've sent to (for monitoring)
        self.contacts_to_monitor: List[str] = []
        
        # Track last seen messages (phone -> last message text)
        self.last_seen_messages: Dict[str, str] = {}
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None
        
        # Initialize Selenium
        self._setup_driver()
        
        # Statistics
        self.success_count = 0
        self.failed_count = 0
        self.total_sent = 0
        self.ai_responses_sent = 0
    
    def _setup_driver(self):
        """Setup Chrome driver with anti-detection features and persistent session"""
        import os
        
        options = webdriver.ChromeOptions()
        
        # Persistent session: Save browser profile to avoid QR code scan each time
        profile_dir = os.path.join(os.getcwd(), "whatsapp_chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
        print(f"💾 Using persistent Chrome profile: {profile_dir}")
        print("   (Your WhatsApp session will be saved - no need to scan QR code next time!)")
        
        # Anti-detection settings
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Additional stealth options
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.wait = WebDriverWait(self.driver, 15)
        
        # Navigate to WhatsApp Web
        print("Opening WhatsApp Web...")
        self.driver.get("https://web.whatsapp.com")
        time.sleep(3)  # Wait for page to load
        
        # Check if already logged in (session exists)
        print("Checking if you're already logged in...")
        try:
            # Wait a bit for page to fully load
            time.sleep(2)
            
            # Check if chat list is visible (means already logged in)
            chat_list = self.driver.find_elements(By.XPATH, '//div[@id="pane-side"] | //div[@data-testid="chat-list"] | //div[contains(@class, "_2Ts6i")]')
            qr_code = self.driver.find_elements(By.XPATH, '//div[@data-ref] | //canvas | //div[contains(@class, "landing-wrapper")]')
            
            if chat_list and len(chat_list) > 0:
                print("✅ You're already logged in! Session restored from previous login.")
                print("   No need to scan QR code - continuing...")
                time.sleep(2)
                return
        except:
            pass
        
        # Not logged in - show QR code instructions
        print("\n" + "="*60)
        print("📱 WHATSAPP WEB LOGIN REQUIRED")
        print("="*60)
        print("\n1. A QR code should appear in the Chrome window")
        print("2. Open WhatsApp on your phone")
        print("3. Go to Settings → Linked Devices")
        print("4. Tap 'Link a Device' and scan the QR code")
        print("5. Wait for WhatsApp Web to load (you'll see your chats)")
        print("\n" + "="*60)
        print("⚠️  IMPORTANT: After you see your chats loaded,")
        print("    come back here and press ENTER to continue!")
        print("="*60)
        print("💡 TIP: After this first login, your session will be saved.")
        print("   Next time you run the script, you won't need to scan QR code!")
        print("="*60 + "\n")
        
        # Try to auto-detect when logged in
        print("Waiting for you to scan QR code and login...")
        try:
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[@id="pane-side"] | //div[@data-testid="chat-list"] | //div[contains(@class, "_2Ts6i")]')
            ))
            print("✅ Detected: You're logged in! Session saved for next time.")
            print("   (You won't need to scan QR code again!)")
            time.sleep(2)
        except TimeoutException:
            print("\n⚠️  Could not auto-detect login. Please confirm:")
            input("Press Enter ONLY after you see your chats loaded in WhatsApp Web...")
            print("✅ Session saved! Next time you won't need to scan QR code.")
    
    def _reset_daily_limit(self):
        """Reset daily usage counter if it's a new day"""
        today = datetime.now().date()
        if self.daily_reset_date < today:
            self.daily_usage = 0
            self.daily_reset_date = today
    
    def check_daily_limit(self):
        """Check if daily limit has been reached"""
        self._reset_daily_limit()
        return self.daily_usage < self.daily_limit
    
    def generate_ai_response(self, customer_message: str, phone: str, context: Optional[str] = None) -> str:
        """
        Generate AI response using OpenAI API
        
        Args:
            customer_message: The message from the customer
            phone: Customer's phone number
            context: Optional context about the customer
        
        Returns:
            AI-generated response
        """
        if not self.ai_enabled:
            return "Thank you for your message. We'll get back to you soon."
        
        try:
            # Get conversation history for this customer
            history = self.conversation_history.get(phone, [])
            
            # Build messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add context if provided
            if context:
                messages.append({"role": "system", "content": f"Customer context: {context}"})
            
            # Add conversation history
            for msg in history[-10:]:  # Last 10 messages for context
                messages.append(msg)
            
            # Add current customer message
            messages.append({"role": "user", "content": customer_message})
            
            # Call OpenAI API
            if not self.openai_client:
                return "Thank you for your message. We'll get back to you soon."
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-3.5-turbo" for cheaper option
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Update conversation history
            if phone not in self.conversation_history:
                self.conversation_history[phone] = []
            
            self.conversation_history[phone].append({"role": "user", "content": customer_message})
            self.conversation_history[phone].append({"role": "assistant", "content": ai_response})
            
            # Keep history manageable (last 20 messages)
            if len(self.conversation_history[phone]) > 20:
                self.conversation_history[phone] = self.conversation_history[phone][-20:]
            
            return ai_response
            
        except Exception as e:
            print(f"⚠️  Error generating AI response: {str(e)}")
            return "Thank you for your message. We'll get back to you soon."
    
    def get_incoming_messages(self) -> List[Dict]:
        """
        Check for new incoming messages in WhatsApp Web
        
        Returns:
            List of new messages with phone number and message text
        """
        try:
            new_messages = []
            
            # Method 1: Check chat list for unread indicators
            # Try multiple selectors for unread chats
            unread_selectors = [
                '//div[contains(@class, "_8nE1Y")]',  # Unread chat indicator
                '//span[contains(@class, "unread")]',
                '//div[@data-testid="unread"]',
                '//div[contains(@aria-label, "unread")]',
                '//span[contains(@aria-label, "unread")]',
            ]
            
            unread_chats = []
            for selector in unread_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        unread_chats = elements
                        break
                except:
                    continue
            
            # Method 2: Check all chats in the list for new messages
            # Get all chat items from the chat list
            chat_list_selectors = [
                '//div[@id="pane-side"]//div[@role="listitem"]',
                '//div[@id="pane-side"]//div[contains(@class, "_8nE1Y")]',
                '//div[@id="pane-side"]//div[contains(@class, "chat")]',
            ]
            
            chat_items = []
            for selector in chat_list_selectors:
                try:
                    items = self.driver.find_elements(By.XPATH, selector)
                    if items:
                        chat_items = items[:10]  # Check top 10 chats
                        break
                except:
                    continue
            
            # If we found unread chats, prioritize those
            chats_to_check = unread_chats[:5] if unread_chats else chat_items[:5]
            
            # Store current URL to restore later
            original_url = self.driver.current_url
            
            for chat in chats_to_check:
                try:
                    # Click on the chat
                    chat.click()
                    time.sleep(2)  # Wait for chat to load
                    
                    # Get phone number from URL
                    current_url = self.driver.current_url
                    if "send?phone=" in current_url:
                        phone = current_url.split("send?phone=")[1].split("&")[0]
                        # Decode URL encoding if needed
                        phone = phone.replace('%2B', '+')
                    else:
                        continue
                    
                    # Get the latest message from the chat
                    # Try multiple selectors for messages
                    message_selectors = [
                        '//div[contains(@class, "message")]//span[contains(@class, "selectable-text")]',
                        '//span[@class="selectable-text copyable-text"]',
                        '//div[@data-testid="conversation-panel-messages"]//span[contains(@class, "selectable-text")]',
                        '//div[@role="application"]//span[contains(@class, "selectable-text")]',
                        '//div[contains(@class, "message-in")]//span',
                        '//div[contains(@class, "message-out")]//span',
                    ]
                    
                    message_elements = []
                    for selector in message_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            if elements:
                                message_elements = elements
                                break
                        except:
                            continue
                    
                    if message_elements:
                        # Get the last message (most recent)
                        latest_message_element = message_elements[-1]
                        latest_message = latest_message_element.text.strip()
                        
                        # Skip if message is empty
                        if not latest_message:
                            continue
                        
                        # Check if this is a new message (not already in history)
                        is_new = False
                        if phone not in self.conversation_history:
                            is_new = True
                        else:
                            # Check if this message is different from the last one we saw
                            last_message = self.conversation_history[phone][-1].get("content", "") if self.conversation_history[phone] else ""
                            if latest_message != last_message:
                                # Check if it's from the user (not from us)
                                # Messages from us usually have different styling
                                try:
                                    # Check if message is incoming (from customer)
                                    parent = latest_message_element.find_element(By.XPATH, './ancestor::div[contains(@class, "message-in") or contains(@class, "message")]')
                                    is_new = True
                                except:
                                    # If we can't determine, assume it's new if different
                                    is_new = True
                        
                        if is_new:
                            new_messages.append({
                                "phone": phone,
                                "message": latest_message,
                                "timestamp": datetime.now()
                            })
                            print(f"📨 Detected new message from {phone}: {latest_message[:50]}...")
                    
                except Exception as e:
                    print(f"⚠️  Error checking chat: {str(e)}")
                    continue
            
            # Restore original URL if we navigated away
            if original_url != self.driver.current_url:
                try:
                    self.driver.get(original_url)
                    time.sleep(1)
                except:
                    pass
            
            return new_messages
            
        except Exception as e:
            print(f"❌ Error checking messages: {str(e)}")
            return []
    
    def send_message_to_contact(self, phone: str, message: str, media_path: Optional[str] = None) -> bool:
        """
        Send a message to a specific contact, optionally with media (video/image)
        
        Args:
            phone: Phone number
            message: Message text (caption if media is provided)
            media_path: Optional path to video/image file to send
        
        Returns:
            True if sent successfully
        """
        try:
            # Format phone number
            phone = phone.replace(' ', '').replace('-', '')
            if not phone.startswith('+'):
                if phone.startswith('966'):
                    phone = '+' + phone
                elif phone.startswith('0'):
                    phone = '+966' + phone[1:]
                else:
                    phone = '+966' + phone
            
            # Open chat
            chat_url = f"https://web.whatsapp.com/send?phone={phone}"
            self.driver.get(chat_url)
            time.sleep(random.uniform(2, 4))
            
            # Find input box
            selectors = [
                '//div[@contenteditable="true"][@data-tab="10"]',
                '//div[@contenteditable="true"][@role="textbox"]',
                '//div[@contenteditable="true"][@data-testid="conversation-compose-box-input"]',
                '//div[@contenteditable="true"]',
            ]
            
            input_box = None
            for selector in selectors:
                try:
                    input_box = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not input_box:
                return False
            
            input_box.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            # If media is provided, type text first (it will become caption), then attach media
            if media_path:
                try:
                    import os
                    if not os.path.exists(media_path):
                        print(f"⚠️  Media file not found: {media_path}")
                        media_path = None
                    else:
                        # Step 1: Type the message text first (it will become the caption)
                        # Use JavaScript to set text to avoid ChromeDriver BMP character limitation (emojis, etc.)
                        if message:
                            print(f"📝 Typing message first (will become caption)...")
                            try:
                                # Use JavaScript to properly set text in contenteditable div (handles emojis and non-BMP characters)
                                self.driver.execute_script("""
                                    var element = arguments[0];
                                    var text = arguments[1];
                                    
                                    // Focus the element first
                                    element.focus();
                                    element.click();
                                    
                                    // Clear any existing content
                                    element.textContent = '';
                                    element.innerText = '';
                                    
                                    // Set the new text
                                    element.textContent = text;
                                    element.innerText = text;
                                    
                                    // Set innerHTML to preserve formatting
                                    element.innerHTML = text.replace(/\\n/g, '<br>');
                                    
                                    // Create and dispatch input event (most important for WhatsApp)
                                    var inputEvent = new InputEvent('input', {
                                        bubbles: true,
                                        cancelable: true,
                                        inputType: 'insertText',
                                        data: text
                                    });
                                    element.dispatchEvent(inputEvent);
                                    
                                    // Also dispatch other events that WhatsApp might listen to
                                    var changeEvent = new Event('change', { bubbles: true });
                                    element.dispatchEvent(changeEvent);
                                    
                                    var keyupEvent = new Event('keyup', { bubbles: true });
                                    element.dispatchEvent(keyupEvent);
                                    
                                    // Force a blur and refocus to ensure WhatsApp recognizes the change
                                    element.blur();
                                    setTimeout(function() {
                                        element.focus();
                                    }, 100);
                                """, input_box, message)
                                time.sleep(2)  # Wait longer for WhatsApp to recognize the text
                                
                                # Verify text was set
                                try:
                                    current_text = input_box.text or input_box.get_attribute('textContent') or ''
                                    if message[:30] in current_text or len(current_text) > 0:
                                        print(f"✅ Message text set via JavaScript: {current_text[:50]}...")
                                    else:
                                        print(f"⚠️  Text might not have been set properly, trying alternative method...")
                                        # Alternative: try typing character by character (slower but more reliable)
                                        input_box.click()
                                        time.sleep(0.5)
                                        for char in message:
                                            try:
                                                input_box.send_keys(char)
                                                time.sleep(0.05)
                                            except:
                                                # Skip characters that can't be sent
                                                pass
                                        print(f"✅ Message text set via character-by-character")
                                except:
                                    print(f"✅ Message text set via JavaScript (verification skipped)")
                            except Exception as e:
                                print(f"⚠️  Error setting text via JavaScript: {str(e)}")
                                # Last resort: try send_keys (might fail with emojis)
                                try:
                                    input_box.click()
                                    time.sleep(0.5)
                                    input_box.send_keys(message)
                                    time.sleep(1)
                                    print(f"✅ Message text set via send_keys")
                                except:
                                    print(f"⚠️  Could not set message text")
                                    pass
                        
                        # Step 2: Wait a bit for chat to fully load
                        time.sleep(1)
                        
                        # Method 1: Try to find attachment button (clip/paperclip icon)
                        attachment_selectors = [
                            '//span[@data-icon="attach"]/..',
                            '//span[@data-icon="attach"]',
                            '//button[@aria-label="Attach"]',
                            '//button[@aria-label*="Attach" or @aria-label*="attach"]',
                            '//button[@data-testid="attach"]',
                            '//div[@data-testid="attach"]',
                            '//span[contains(@class, "attach")]',
                            '//div[contains(@class, "attach")]',
                            '//button[contains(@class, "attach")]',
                            # Try finding by position near input box
                            '//div[@contenteditable="true"]/../..//span[@data-icon="attach"]',
                            '//div[@contenteditable="true"]/../..//button[contains(@aria-label, "Attach")]',
                        ]
                        
                        attachment_button = None
                        for selector in attachment_selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, selector)
                                if elements:
                                    # Try to find the one that's visible and clickable
                                    for elem in elements:
                                        try:
                                            if elem.is_displayed() and elem.is_enabled():
                                                attachment_button = elem
                                                break
                                        except:
                                            continue
                                    if attachment_button:
                                        break
                            except:
                                continue
                        
                        # If still not found, try JavaScript to click it directly
                        if not attachment_button:
                            try:
                                clicked = self.driver.execute_script("""
                                    var selectors = [
                                        '[data-icon="attach"]',
                                        '[aria-label*="Attach"]',
                                        '[data-testid="attach"]'
                                    ];
                                    for (var i = 0; i < selectors.length; i++) {
                                        var elem = document.querySelector(selectors[i]);
                                        if (elem && elem.offsetParent !== null) {
                                            elem.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                """)
                                if clicked:
                                    print(f"📎 Attachment button clicked via JavaScript")
                                    time.sleep(1.5)
                                    # Now try to find file input
                                    file_inputs = self.driver.find_elements(By.XPATH, '//input[@type="file"]')
                                    if file_inputs:
                                        file_input = file_inputs[0]
                            except:
                                pass
                        
                        # Method 2: Try to find file input directly (sometimes it's visible)
                        file_input_selectors = [
                            '//input[@type="file"]',
                            '//input[@accept]',
                            '//input[@accept*="video"]',
                            '//input[@accept*="image"]',
                        ]
                        
                        file_input = None
                        for selector in file_input_selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, selector)
                                if elements:
                                    file_input = elements[0]
                                    break
                            except:
                                continue
                        
                        # If we found attachment button, click it first
                        if attachment_button:
                            try:
                                attachment_button.click()
                                print(f"📎 Attachment menu opened")
                                time.sleep(1.5)  # Wait for menu to appear
                                
                                # Determine if it's a video or image based on file extension
                                file_ext = os.path.splitext(media_path)[1].lower()
                                is_video = file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']
                                is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
                                
                                # For videos and images, select "Photos & Videos" option (not "Document")
                                if is_video or is_image:
                                    print(f"🎬 Selecting 'Photos & Videos' option (not Document)...")
                                    time.sleep(0.5)  # Wait a bit more for menu to fully appear
                                    
                                    # First try JavaScript to find and click "Photos & Videos" option
                                    clicked = self.driver.execute_script("""
                                        // Find all menu items
                                        var menuItems = document.querySelectorAll('[role="button"], [role="menuitem"], button, div[tabindex]');
                                        var photosVideosOption = null;
                                        
                                        for (var i = 0; i < menuItems.length; i++) {
                                            var item = menuItems[i];
                                            var ariaLabel = item.getAttribute('aria-label') || '';
                                            var text = item.textContent || item.innerText || '';
                                            
                                            // Check if this is the Photos & Videos option
                                            if ((ariaLabel.toLowerCase().includes('photo') && ariaLabel.toLowerCase().includes('video')) ||
                                                (ariaLabel.toLowerCase().includes('photos') && ariaLabel.toLowerCase().includes('videos')) ||
                                                text.toLowerCase().includes('photo') && text.toLowerCase().includes('video')) {
                                                
                                                // Make sure it's visible
                                                if (item.offsetParent !== null) {
                                                    photosVideosOption = item;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        if (photosVideosOption) {
                                            photosVideosOption.click();
                                            return true;
                                        }
                                        
                                        // Alternative: Look for data-testid
                                        var testIdElement = document.querySelector('[data-testid*="photo"], [data-testid*="video"], [data-testid*="attach-photo"]');
                                        if (testIdElement && testIdElement.offsetParent !== null) {
                                            testIdElement.click();
                                            return true;
                                        }
                                        
                                        return false;
                                    """)
                                    
                                    if clicked:
                                        print(f"✅ Selected 'Photos & Videos' option via JavaScript")
                                        time.sleep(1.5)  # Wait for file picker to appear
                                    else:
                                        # Fallback: Try XPath selectors
                                        print(f"⚠️  JavaScript method didn't find option, trying XPath...")
                                        photos_videos_selectors = [
                                            '//div[@role="button"][contains(@aria-label, "Photos") or contains(@aria-label, "Videos")]',
                                            '//div[@role="menuitem"][contains(@aria-label, "Photos") or contains(@aria-label, "Videos")]',
                                            '//button[contains(@aria-label, "Photos") or contains(@aria-label, "Videos")]',
                                            '//span[contains(text(), "Photos") or contains(text(), "Videos")]/..',
                                            '//div[contains(@class, "menu")]//div[contains(@aria-label, "Photos") or contains(@aria-label, "Videos")]',
                                            '//div[@data-testid="attach-photos-videos"]',
                                            '//div[@data-testid*="photo"]',
                                            '//div[@data-testid*="video"]',
                                        ]
                                        
                                        photos_videos_option = None
                                        for selector in photos_videos_selectors:
                                            try:
                                                elements = self.driver.find_elements(By.XPATH, selector)
                                                if elements:
                                                    for elem in elements:
                                                        try:
                                                            if elem.is_displayed() and elem.is_enabled():
                                                                photos_videos_option = elem
                                                                break
                                                        except:
                                                            continue
                                                    if photos_videos_option:
                                                        break
                                            except:
                                                continue
                                        
                                        if photos_videos_option:
                                            try:
                                                photos_videos_option.click()
                                                print(f"✅ Selected 'Photos & Videos' option via XPath")
                                                time.sleep(1.5)  # Wait for file picker to appear
                                            except Exception as e:
                                                print(f"⚠️  Could not click 'Photos & Videos' option: {str(e)}")
                                                # Continue anyway, might still work
                                        else:
                                            print(f"⚠️  Could not find 'Photos & Videos' option, will try default file input...")
                                            print(f"⚠️  Note: Video might be sent as document instead of playable video")
                                
                                # Now try to find file input again (it appears after clicking attach/selecting option)
                                # For videos, prefer file inputs that accept video files
                                if is_video:
                                    # First try to find file input that accepts video
                                    video_input_selectors = [
                                        '//input[@type="file"][@accept*="video"]',
                                        '//input[@type="file"][@accept*="mp4"]',
                                        '//input[@type="file"][@accept*="mov"]',
                                    ]
                                    for selector in video_input_selectors:
                                        try:
                                            elements = self.driver.find_elements(By.XPATH, selector)
                                            if elements:
                                                file_input = elements[0]
                                                print(f"✅ Found video file input")
                                                break
                                        except:
                                            continue
                                
                                # If not found, try general file input selectors
                                if not file_input:
                                    for selector in file_input_selectors:
                                        try:
                                            file_input = self.wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                                            break
                                        except:
                                            continue
                            except Exception as e:
                                print(f"⚠️  Error clicking attachment button: {str(e)}")
                        
                        # If we have file input, send the file
                        if file_input:
                            try:
                                abs_path = os.path.abspath(media_path)
                                file_input.send_keys(abs_path)
                                print(f"📎 File attached: {os.path.basename(media_path)}")
                                
                                # Wait for file to start uploading (check for upload progress)
                                time.sleep(2)
                                
                                # Wait for upload to complete (check for caption box or send button to appear)
                                try:
                                    # Wait for caption box or send button to become available
                                    self.wait.until(EC.presence_of_element_located(
                                        (By.XPATH, '//div[@contenteditable="true"] | //span[@data-icon="send"] | //button[@aria-label="Send"]')
                                    ), timeout=10)
                                    print(f"✅ File upload completed")
                                except:
                                    print(f"⚠️  Upload may still be in progress, continuing...")
                                
                                # The message text was already typed in the input box before attaching,
                                # so it should automatically become the caption. Just verify it's still there.
                                if message:
                                    # Wait a bit for caption box to appear after file upload
                                    time.sleep(2)
                                    
                                    # Check if the message text is already in the caption box
                                    # (it should be, since we typed it before attaching)
                                    caption_selectors = [
                                        '//div[@contenteditable="true"][@data-testid="caption"]',
                                        '//div[@contenteditable="true"][@placeholder*="caption" or @placeholder*="Caption" or @placeholder*="Add a caption" or @placeholder*="Type a message"]',
                                        '//div[@contenteditable="true"][@role="textbox"]',
                                        '//div[@contenteditable="true"][@data-tab="10"]',
                                        '//div[@contenteditable="true"]',
                                    ]
                                    
                                    caption_box = None
                                    for selector in caption_selectors:
                                        try:
                                            elements = self.driver.find_elements(By.XPATH, selector)
                                            if elements:
                                                # Find the one that's visible and contains our text or is the caption box
                                                for elem in elements:
                                                    try:
                                                        if elem.is_displayed() and elem.is_enabled():
                                                            # Check if it already has our message text
                                                            elem_text = elem.text or elem.get_attribute('textContent') or ''
                                                            if message[:20] in elem_text or 'caption' in (elem.get_attribute('placeholder') or '').lower():
                                                                caption_box = elem
                                                                break
                                                    except:
                                                        continue
                                                if caption_box:
                                                    break
                                        except:
                                            continue
                                    
                                    if caption_box:
                                        # Verify the text is there, if not, add it
                                        try:
                                            caption_text = caption_box.text or caption_box.get_attribute('textContent') or ''
                                            if message[:20] not in caption_text:
                                                # Text not there, add it using JavaScript (handles emojis)
                                                try:
                                                    self.driver.execute_script("""
                                                        var element = arguments[0];
                                                        var text = arguments[1];
                                                        element.focus();
                                                        element.textContent = text;
                                                        element.innerText = text;
                                                        // Trigger input event to notify WhatsApp
                                                        var event = new Event('input', { bubbles: true });
                                                        element.dispatchEvent(event);
                                                    """, caption_box, message)
                                                    time.sleep(1)
                                                    print(f"📝 Caption verified/added via JavaScript: {message[:50]}...")
                                                except:
                                                    # Fallback to send_keys (might fail with emojis)
                                                    try:
                                                        caption_box.click()
                                                        time.sleep(0.5)
                                                        caption_box.send_keys(Keys.CONTROL + "a")
                                                        time.sleep(0.2)
                                                        caption_box.send_keys(message)
                                                        time.sleep(1)
                                                        print(f"📝 Caption verified/added: {message[:50]}...")
                                                    except:
                                                        print(f"⚠️  Could not add caption")
                                            else:
                                                print(f"✅ Caption already present: {message[:50]}...")
                                        except Exception as e:
                                            print(f"⚠️  Error verifying caption: {str(e)}")
                                    else:
                                        print(f"ℹ️  Caption box not found, but text was typed before attachment (should work)")
                                
                                # Mark that media was successfully attached
                                media_attached = True
                            except Exception as e:
                                print(f"⚠️  Error uploading file: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                media_path = None  # Fall back to text-only
                                media_attached = False
                        else:
                            print(f"⚠️  Could not find file input. Trying alternative methods...")
                            media_attached = False
                            
                            # Alternative Method 1: Use JavaScript to find and trigger file input
                            try:
                                # Create a file input element if it doesn't exist
                                file_input_js = self.driver.execute_script("""
                                    // Try to find existing file input
                                    var inputs = document.querySelectorAll('input[type="file"]');
                                    if (inputs.length > 0) {
                                        return inputs[0];
                                    }
                                    
                                    // If not found, try to find attachment button and click it
                                    var attachBtn = document.querySelector('[data-icon="attach"]') || 
                                                   document.querySelector('[aria-label*="Attach"]') ||
                                                   document.querySelector('[data-testid="attach"]');
                                    if (attachBtn) {
                                        attachBtn.click();
                                        // Wait a bit for file input to appear
                                        setTimeout(function(){}, 1000);
                                        inputs = document.querySelectorAll('input[type="file"]');
                                        if (inputs.length > 0) {
                                            return inputs[0];
                                        }
                                    }
                                    return null;
                                """)
                                
                                if file_input_js:
                                    # Get the file input element
                                    file_inputs = self.driver.find_elements(By.XPATH, '//input[@type="file"]')
                                    if file_inputs:
                                        file_input = file_inputs[0]
                                        abs_path = os.path.abspath(media_path)
                                        file_input.send_keys(abs_path)
                                        print(f"📎 File attached (via JS): {os.path.basename(media_path)}")
                                        time.sleep(3)
                                        
                                        # Add caption if message provided
                                        if message:
                                            caption_box = self.wait.until(EC.element_to_be_clickable(
                                                (By.XPATH, '//div[@contenteditable="true"]')
                                            ), timeout=5)
                                            if caption_box:
                                                caption_box.click()
                                                time.sleep(0.5)
                                                caption_box.send_keys(message)
                                                time.sleep(1)
                                                print(f"📝 Caption added")
                                    else:
                                        print(f"⚠️  File input not accessible. Trying direct click method...")
                                        # Try clicking attachment button directly with JS
                                        self.driver.execute_script("""
                                            var btn = document.querySelector('[data-icon="attach"]') || 
                                                     document.querySelector('[aria-label*="Attach"]');
                                            if (btn) btn.click();
                                        """)
                                        time.sleep(2)
                                        # Try again
                                        file_inputs = self.driver.find_elements(By.XPATH, '//input[@type="file"]')
                                        if file_inputs:
                                            file_input = file_inputs[0]
                                            abs_path = os.path.abspath(media_path)
                                            file_input.send_keys(abs_path)
                                            print(f"📎 File attached (after JS click): {os.path.basename(media_path)}")
                                            time.sleep(3)
                                            if message:
                                                caption_box = self.wait.until(EC.element_to_be_clickable(
                                                    (By.XPATH, '//div[@contenteditable="true"]')
                                                ), timeout=5)
                                                if caption_box:
                                                    caption_box.send_keys(message)
                                                    time.sleep(1)
                                        else:
                                            print(f"⚠️  Could not access file input. Sending text-only message.")
                                            media_path = None
                                else:
                                    print(f"⚠️  Could not find file input via JavaScript. Sending text-only message.")
                                    media_path = None
                            except Exception as e:
                                print(f"⚠️  Alternative method failed: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                media_path = None
                        
                        if not file_input and not attachment_button:
                            print(f"⚠️  Could not find attachment button or file input.")
                            # Debug: Check what attachment-related elements exist
                            try:
                                debug_info = self.driver.execute_script("""
                                    var info = {
                                        attachButtons: [],
                                        fileInputs: [],
                                        allButtons: []
                                    };
                                    
                                    // Check for attachment buttons
                                    var attachSelectors = [
                                        '[data-icon="attach"]',
                                        '[aria-label*="Attach"]',
                                        '[data-testid="attach"]',
                                        '[class*="attach"]'
                                    ];
                                    
                                    attachSelectors.forEach(function(sel) {
                                        var elems = document.querySelectorAll(sel);
                                        for (var i = 0; i < elems.length; i++) {
                                            info.attachButtons.push({
                                                selector: sel,
                                                tag: elems[i].tagName,
                                                class: elems[i].className,
                                                ariaLabel: elems[i].getAttribute('aria-label')
                                            });
                                        }
                                    });
                                    
                                    // Check for file inputs
                                    var inputs = document.querySelectorAll('input[type="file"]');
                                    for (var i = 0; i < inputs.length; i++) {
                                        info.fileInputs.push({
                                            accept: inputs[i].getAttribute('accept'),
                                            id: inputs[i].id,
                                            class: inputs[i].className
                                        });
                                    }
                                    
                                    return info;
                                """)
                                print(f"🔍 Debug info: Found {len(debug_info.get('attachButtons', []))} attachment buttons, {len(debug_info.get('fileInputs', []))} file inputs")
                            except:
                                pass
                            print(f"⚠️  Sending text-only message.")
                            media_path = None
                            
                except Exception as e:
                    print(f"⚠️  Error attaching media: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    media_path = None  # Fall back to text-only
            
            # Type message (only if no media was attached, or if media failed)
            # If media was attached, message was already typed before attachment
            if not media_path or (media_path and not message):
                if message:
                    try:
                        # Use JavaScript to set text (handles emojis and non-BMP characters)
                        self.driver.execute_script("""
                            var element = arguments[0];
                            var text = arguments[1];
                            element.focus();
                            element.textContent = text;
                            element.innerText = text;
                            // Trigger input event to notify WhatsApp
                            var event = new Event('input', { bubbles: true });
                            element.dispatchEvent(event);
                            // Also trigger keyup event
                            var keyupEvent = new Event('keyup', { bubbles: true });
                            element.dispatchEvent(keyupEvent);
                        """, input_box, message)
                        time.sleep(random.uniform(1, 2))
                        print(f"✅ Message text set via JavaScript")
                    except Exception as e:
                        print(f"⚠️  Error setting text via JavaScript: {str(e)}, trying send_keys...")
                        # Fallback: try send_keys for simple text (might fail with emojis)
                        try:
                            input_box.send_keys(Keys.CONTROL + "a")
                            time.sleep(0.2)
                            input_box.send_keys(message)
                            time.sleep(random.uniform(1, 2))
                        except:
                            print(f"⚠️  Could not set message text")
                            pass
            
            # Send message - wait longer if media was attached
            # Check if media was actually attached
            media_attached = media_path and os.path.exists(media_path) if media_path else False
            
            if media_attached:
                # Wait longer for media to finish uploading
                print(f"⏳ Waiting for media to finish uploading...")
                wait_before_send = 5
                time.sleep(wait_before_send)
                
                # Wait for send button to become enabled (media upload complete)
                try:
                    self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//span[@data-icon="send"]/.. | //button[@aria-label="Send"] | //button[@data-testid="send"]')
                    ), timeout=15)
                    print(f"✅ Media upload completed, send button ready")
                except:
                    print(f"⚠️  Send button not ready yet, continuing anyway...")
            else:
                wait_before_send = 1
                time.sleep(wait_before_send)
            
            send_selectors = [
                '//span[@data-icon="send"]/..',
                '//button[@aria-label="Send"]',
                '//button[@data-testid="send"]',
                '//span[@data-icon="send"]',
                '//button[contains(@aria-label, "Send")]',
            ]
            
            sent = False
            for selector in send_selectors:
                try:
                    send_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)), timeout=5)
                    if send_button and send_button.is_displayed() and send_button.is_enabled():
                        send_button.click()
                        sent = True
                        print(f"✅ Send button clicked")
                        break
                except:
                    continue
            
            if not sent:
                # Try pressing Enter as fallback
                print(f"⚠️  Send button not found, trying Enter key...")
                try:
                    # Find the active input/caption box
                    active_input = self.driver.switch_to.active_element
                    if active_input:
                        active_input.send_keys(Keys.RETURN)
                        print(f"✅ Sent via Enter key")
                        sent = True
                except:
                    # Last resort: try to find any input and press Enter
                    try:
                        # Find caption box or input box
                        caption_or_input = self.driver.find_elements(By.XPATH, '//div[@contenteditable="true"]')
                        if caption_or_input:
                            caption_or_input[-1].send_keys(Keys.RETURN)
                            print(f"✅ Sent via Enter key (fallback)")
                            sent = True
                        else:
                            input_box.send_keys(Keys.RETURN)
                            print(f"✅ Sent via Enter key (input box)")
                            sent = True
                    except Exception as e:
                        print(f"⚠️  Could not send message: {str(e)}")
                        return False
            
            # Wait for message to actually send (longer for media)
            wait_after_send = 5 if media_path else 2
            time.sleep(wait_after_send)
            
            # Verify message was sent by checking for sent indicator
            if media_path:
                try:
                    # Wait for sent checkmark or message to appear in chat
                    self.wait.until(EC.presence_of_element_located(
                        (By.XPATH, '//span[@data-icon="msg-dblcheck"] | //span[@data-icon="msg-check"] | //div[contains(@class, "message-out")]')
                    ), timeout=10)
                    print(f"✅ Media message sent successfully")
                except:
                    print(f"⚠️  Could not verify media was sent, but send was attempted")
            
            return True
            
        except Exception as e:
            print(f"Error sending message to {phone}: {str(e)}")
            return False
    
    def check_contact_for_messages(self, phone: str) -> Optional[Dict]:
        """
        Check a specific contact for new messages (including read messages)
        Only checks contacts we've sent to
        
        Args:
            phone: Phone number to check
        
        Returns:
            Dict with phone and message if new message found, None otherwise
        """
        try:
            # Format phone number
            phone_original = phone
            phone = phone.replace(' ', '').replace('-', '')
            if not phone.startswith('+'):
                if phone.startswith('966'):
                    phone = '+' + phone
                elif phone.startswith('0'):
                    phone = '+966' + phone[1:]
                else:
                    phone = '+966' + phone
            
            # Open chat
            chat_url = f"https://web.whatsapp.com/send?phone={phone}"
            self.driver.get(chat_url)
            time.sleep(3)  # Wait for chat to load
            
            # Get ALL messages - try multiple methods
            all_messages = []
            message_elements = []
            
            # Method 1: Try to get messages by various selectors
            message_selectors = [
                '//div[contains(@class, "message")]//span[contains(@class, "selectable-text")]',
                '//span[@class="selectable-text copyable-text"]',
                '//div[@data-testid="conversation-panel-messages"]//span[contains(@class, "selectable-text")]',
                '//div[@role="application"]//span[contains(@class, "selectable-text")]',
                '//div[contains(@class, "message-in")]//span[contains(@class, "selectable-text")]',
                '//div[contains(@class, "message-out")]//span[contains(@class, "selectable-text")]',
                '//span[contains(@class, "selectable-text")]',
            ]
            
            for selector in message_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        message_elements = elements
                        break
                except:
                    continue
            
            # Get all message texts
            if message_elements:
                for element in message_elements:
                    try:
                        msg_text = element.text.strip()
                        if msg_text and msg_text not in all_messages:
                            all_messages.append(msg_text)
                    except:
                        continue
            
            if not all_messages:
                # Try alternative method - get all text in the message area
                try:
                    message_area = self.driver.find_element(By.XPATH, '//div[@data-testid="conversation-panel-messages"] | //div[@role="application"]')
                    all_text = message_area.text
                    if all_text:
                        # Split by lines and get non-empty lines
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        all_messages = lines
                except:
                    pass
            
            if all_messages:
                # Get the latest message (most recent - last in list)
                latest_message = all_messages[-1]
                
                # Check if this is a new message we haven't seen
                last_seen = self.last_seen_messages.get(phone, "")
                
                # Debug: print what we found
                print(f"🔍 Checking {phone}: Latest='{latest_message[:50]}...', Last seen='{last_seen[:50] if last_seen else 'None'}...'")
                
                # If it's different from what we last saw, it's potentially new
                if latest_message != last_seen:
                    # Check if it's from the customer (not from us)
                    # Get the last message element to check its parent
                    is_from_customer = False
                    
                    try:
                        # Try to find the element containing the latest message
                        latest_element = None
                        for element in message_elements:
                            try:
                                if element.text.strip() == latest_message:
                                    latest_element = element
                                    break
                            except:
                                continue
                        
                        if latest_element:
                            # Check parent classes to determine if it's incoming or outgoing
                            try:
                                parent = latest_element.find_element(By.XPATH, './ancestor::div[contains(@class, "message")]')
                                parent_class = parent.get_attribute("class") or ""
                                
                                # Incoming messages have "message-in" class
                                if "message-in" in parent_class:
                                    is_from_customer = True
                                # Outgoing messages have "message-out" class
                                elif "message-out" in parent_class:
                                    is_from_customer = False
                                else:
                                    # If we can't determine, check if it matches our last sent message
                                    # If it doesn't match our conversation history, assume it's from customer
                                    if phone in self.conversation_history:
                                        last_ai_msg = None
                                        for msg_item in reversed(self.conversation_history[phone]):
                                            if msg_item.get("role") == "assistant":
                                                last_ai_msg = msg_item.get("content", "")
                                                break
                                        
                                        if last_ai_msg and latest_message != last_ai_msg:
                                            is_from_customer = True
                                    else:
                                        # No history, assume it's from customer if different
                                        is_from_customer = True
                            except:
                                # If we can't determine, check conversation history
                                if phone in self.conversation_history:
                                    last_ai_msg = None
                                    for msg_item in reversed(self.conversation_history[phone]):
                                        if msg_item.get("role") == "assistant":
                                            last_ai_msg = msg_item.get("content", "")
                                            break
                                    
                                    # If it's different from our last message, assume it's from customer
                                    if last_ai_msg and latest_message != last_ai_msg:
                                        is_from_customer = True
                                    elif not last_ai_msg:
                                        is_from_customer = True
                                else:
                                    # No history, assume it's from customer
                                    is_from_customer = True
                    except Exception as e:
                        # If we can't determine, check if it's different from our last message
                        if phone in self.conversation_history:
                            last_ai_msg = None
                            for msg_item in reversed(self.conversation_history[phone]):
                                if msg_item.get("role") == "assistant":
                                    last_ai_msg = msg_item.get("content", "")
                                    break
                            
                            if last_ai_msg and latest_message != last_ai_msg:
                                is_from_customer = True
                        else:
                            is_from_customer = True
                    
                    if is_from_customer:
                        self.last_seen_messages[phone] = latest_message
                        print(f"✅ New customer message detected from {phone}")
                        return {
                            "phone": phone,
                            "message": latest_message,
                            "timestamp": datetime.now()
                        }
                    else:
                        print(f"⏭️  Skipping - message is from us, not customer")
            
            return None
            
        except Exception as e:
            print(f"⚠️  Error checking {phone}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def monitor_and_respond(self, check_interval: int = 10):
        """
        Monitor incoming messages and respond automatically
        Only monitors contacts we've sent messages to
        
        Args:
            check_interval: How often to check for new messages (seconds)
        """
        if not self.ai_enabled:
            print("⚠️  AI is not enabled. Cannot monitor messages.")
            return
        
        if not self.contacts_to_monitor:
            print("⚠️  No contacts to monitor. Send messages first.")
            return
        
        self.monitoring = True
        print(f"\n🤖 AI Monitoring Started - Checking every {check_interval} seconds")
        print(f"   Monitoring {len(self.contacts_to_monitor)} contact(s) we've contacted:")
        for contact in self.contacts_to_monitor:
            print(f"      - {contact}")
        print("\n   Checking for new messages (including read messages)")
        print("   Press Ctrl+C to stop monitoring\n")
        
        try:
            cycle_count = 0
            while self.monitoring:
                cycle_count += 1
                print(f"\n🔄 Check cycle #{cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Only check contacts we've sent to
                for phone in self.contacts_to_monitor:
                    try:
                        print(f"   Checking {phone}...")
                        msg = self.check_contact_for_messages(phone)
                        if msg:
                            customer_message = msg["message"]
                            phone_num = msg["phone"]
                            
                            print(f"\n📨 New message from {phone_num}:")
                            print(f"   {customer_message}")
                            
                            # Generate AI response
                            print("🤖 Generating AI response...")
                            ai_response = self.generate_ai_response(customer_message, phone_num)
                            
                            print(f"💬 AI Response: {ai_response}")
                            
                            # Send response
                            if self.send_message_to_contact(phone_num, ai_response):
                                print(f"✅ Response sent to {phone_num}")
                                self.ai_responses_sent += 1
                            else:
                                print(f"❌ Failed to send response to {phone_num}")
                        else:
                            print(f"   No new messages from {phone}")
                    except Exception as e:
                        print(f"⚠️  Error processing {phone}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Small delay between checking each contact
                time.sleep(2)
                
                # Wait before next check cycle
                print(f"   ⏳ Waiting {check_interval} seconds before next check...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            self.monitoring = False
        except Exception as e:
            print(f"\n❌ Error in monitoring: {str(e)}")
            self.monitoring = False
    
    def start_monitoring(self, check_interval: int = 10):
        """
        Start monitoring in a separate thread
        
        Args:
            check_interval: How often to check for new messages (seconds)
        """
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("⚠️  Monitoring already running")
            return
        
        self.monitor_thread = threading.Thread(
            target=self.monitor_and_respond,
            args=(check_interval,),
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring incoming messages"""
        self.monitoring = False
        print("⏹️  Stopping monitoring...")
    
    def send_bulk_messages(self, contacts_list, message_template, prioritize_engaged=True):
        """
        Send bulk messages (same as original class)
        """
        # Import the original method or implement it here
        # For now, this is a placeholder - you can copy from the original class
        print("Bulk sending functionality - use the original class or implement here")
    
    def close(self):
        """Close the browser"""
        self.stop_monitoring()
        if self.driver:
            self.driver.quit()
            print("Browser closed.")
            print(f"\n📊 Final Statistics:")
            print(f"   Messages sent: {self.total_sent}")
            print(f"   AI responses sent: {self.ai_responses_sent}")
            print(f"   Conversations handled: {len(self.conversation_history)}")

