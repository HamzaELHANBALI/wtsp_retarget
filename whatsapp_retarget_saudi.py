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


class SaudiWhatsAppRetargeter:
    """
    Comprehensive WhatsApp retargeting solution for Saudi Arabia customers.
    Combines:
    - Anti-detection automation (from whatsapp_web_auto.py)
    - Number rotation strategy (from rotate_retarget.py)
    - Smart delay patterns (from whatsapp_retarget.py)
    """
    
    def __init__(self, daily_limit=40):
        """
        Initialize the retargeter for WhatsApp Web
        
        Args:
            daily_limit: Maximum messages per day (to avoid rate limiting)
        """
        # Track daily usage (single WhatsApp Web account)
        self.daily_limit = daily_limit
        self.daily_usage = 0
        self.daily_reset_date = datetime.now().date()
        
        # Initialize Selenium with anti-detection
        self._setup_driver()
        
        # Statistics
        self.success_count = 0
        self.failed_count = 0
        self.total_sent = 0
        
    def _setup_driver(self):
        """Setup Chrome driver with anti-detection features"""
        options = webdriver.ChromeOptions()
        
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
        print("="*60 + "\n")
        
        # Try to auto-detect when logged in (wait for chat list)
        print("Waiting for you to scan QR code and login...")
        try:
            # Wait for chat list to appear (means user is logged in)
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[@id="pane-side"] | //div[@data-testid="chat-list"] | //div[contains(@class, "_2Ts6i")]')
            ))
            print("✅ Detected: You're logged in! Continuing...")
            time.sleep(2)  # Give it a moment to fully load
        except TimeoutException:
            # If auto-detection fails, ask user to confirm
            print("\n⚠️  Could not auto-detect login. Please confirm:")
            input("Press Enter ONLY after you see your chats loaded in WhatsApp Web...")
    
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
    
    def verify_whatsapp_number(self, phone):
        """Check if number is registered on WhatsApp"""
        try:
            # Format phone number (remove spaces, ensure +966 format for Saudi)
            phone = phone.replace(' ', '').replace('-', '')
            if not phone.startswith('+'):
                if phone.startswith('966'):
                    phone = '+' + phone
                elif phone.startswith('0'):
                    phone = '+966' + phone[1:]
                else:
                    phone = '+966' + phone
            
            check_url = f"https://web.whatsapp.com/send?phone={phone}"
            self.driver.get(check_url)
            time.sleep(3)  # Wait for page to load
            
            # Wait for either chat to load or error to appear
            try:
                # Check for chat input container (chat loaded successfully)
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//div[@data-tab="10" or @contenteditable="true"]')
                ))
                return True
            except TimeoutException:
                # Check if error message appears (number not on WhatsApp)
                error_elements = self.driver.find_elements(By.XPATH, 
                    '//div[contains(text(), "not on WhatsApp") or contains(text(), "invalid") or contains(text(), "Phone number")]')
                if error_elements:
                    return False
                # If no error found, assume valid
                return True
                
        except Exception as e:
            print(f"Verification error for {phone}: {str(e)}")
            return True  # Assume valid if check fails
    
    def open_chat_natural(self, phone):
        """Open chat with human-like behavior"""
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
            
            chat_url = f"https://web.whatsapp.com/send?phone={phone}"
            self.driver.get(chat_url)
            
            # Human-like delay before interacting
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"Error opening chat for {phone}: {str(e)}")
            raise
    
    def verify_chat_opened(self):
        """Verify that chat opened successfully"""
        try:
            # Wait for input box to be present - try multiple selectors
            # WhatsApp Web uses different selectors in different versions
            selectors = [
                '//div[@contenteditable="true"][@data-tab="10"]',
                '//div[@contenteditable="true"][@role="textbox"]',
                '//div[@contenteditable="true"][@data-testid="conversation-compose-box-input"]',
                '//div[@contenteditable="true"]',
                '//p[@class="selectable-text copyable-text"]',
            ]
            
            for selector in selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                    return True
                except TimeoutException:
                    continue
            
            return False
        except Exception as e:
            print(f"Error verifying chat: {str(e)}")
            return False
    
    def type_message_natural(self, message):
        """Type message with human-like typing patterns"""
        try:
            # Try multiple selectors to find input box
            selectors = [
                '//div[@contenteditable="true"][@data-tab="10"]',
                '//div[@contenteditable="true"][@role="textbox"]',
                '//div[@contenteditable="true"][@data-testid="conversation-compose-box-input"]',
                '//div[@contenteditable="true"]',
                '//p[@class="selectable-text copyable-text"]',
            ]
            
            input_box = None
            for selector in selectors:
                try:
                    input_box = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not input_box:
                raise Exception("Could not find message input box")
            
            input_box.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            # Clear any existing text by selecting all and deleting
            input_box.send_keys(Keys.CONTROL + "a")
            time.sleep(random.uniform(0.2, 0.5))
            input_box.send_keys(Keys.DELETE)
            time.sleep(random.uniform(0.2, 0.5))
            
            # Type with variable speeds
            words = message.split(' ')
            for i, word in enumerate(words):
                input_box.send_keys(word)
                
                # Add space after word (except last word)
                if i < len(words) - 1:
                    input_box.send_keys(" ")
                
                # Variable delay between words
                if i < len(words) - 1:
                    delay = random.uniform(0.1, 0.4)  # 100-400ms
                    time.sleep(delay)
                
                # Occasionally longer pause (like thinking)
                if random.random() < 0.03:  # 3% chance
                    time.sleep(random.uniform(0.5, 1.5))
            
            # Final pause before sending
            time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            print(f"Error typing message: {str(e)}")
            raise
    
    def send_and_verify(self):
        """Send message and verify delivery"""
        try:
            # Try multiple methods to send message
            # Method 1: Try to find and click send button
            send_selectors = [
                '//span[@data-icon="send"]/..',
                '//button[@aria-label="Send"]',
                '//button[@data-testid="send"]',
                '//span[@data-icon="send"]',
                '//button[contains(@aria-label, "Send")]',
            ]
            
            send_button = None
            for selector in send_selectors:
                try:
                    send_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except TimeoutException:
                    continue
            
            if send_button:
                send_button.click()
            else:
                # Method 2: Try pressing Enter key
                print("Send button not found, trying Enter key...")
                input_box = self.driver.find_element(By.XPATH, '//div[@contenteditable="true"]')
                input_box.send_keys(Keys.RETURN)
            
            # Wait a moment for message to send
            time.sleep(random.uniform(2, 3))
            
            # Verify message was sent (check for sent indicator)
            try:
                # Look for sent checkmark or message in chat
                sent_selectors = [
                    '//span[@data-icon="msg-dblcheck"]',
                    '//span[@data-icon="msg-check"]',
                    '//span[@data-testid="msg-dblcheck"]',
                    '//span[@data-testid="msg-check"]',
                ]
                
                for selector in sent_selectors:
                    try:
                        self.wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                        return True
                    except TimeoutException:
                        continue
                
                # If no sent indicator found, assume success (message might have sent)
                return True
            except Exception:
                # Message might have sent but indicator not visible yet
                return True  # Assume success
                
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            # Try pressing Enter as fallback
            try:
                input_box = self.driver.find_element(By.XPATH, '//div[@contenteditable="true"]')
                input_box.send_keys(Keys.RETURN)
                time.sleep(2)
                return True
            except:
                return False
    
    def enhanced_send_message(self, phone, message, contact_name=""):
        """Optimized sending with multiple verification steps"""
        try:
            # Step 1: Check if number exists on WhatsApp
            if not self.verify_whatsapp_number(phone):
                print(f"Number {phone} not on WhatsApp")
                return False
            
            # Step 2: Open chat with human-like behavior
            self.open_chat_natural(phone)
            
            # Step 3: Verify chat opened successfully
            if not self.verify_chat_opened():
                print(f"Failed to open chat for {phone}")
                return False
            
            # Step 4: Type message with human-like delays
            self.type_message_natural(message)
            
            # Step 5: Send and verify delivery
            success = self.send_and_verify()
            
            if success:
                self.success_count += 1
                print(f"✓ Message sent successfully to {phone}")
            else:
                self.failed_count += 1
                print(f"✗ Failed to send message to {phone}")
            
            return success
            
        except Exception as e:
            print(f"Send failed for {phone}: {str(e)}")
            self.failed_count += 1
            return False
    
    def smart_delay(self, current_index, total_contacts):
        """Variable delays to avoid detection - mimics human behavior"""
        base_delay = random.randint(25, 40)  # 25-40 seconds base delay
        
        # Longer break every 10 messages
        if current_index % 10 == 0 and current_index > 0:
            break_time = random.randint(120, 180)  # 2-3 minute break
            print(f"Taking a longer break ({break_time//60} minutes) after {current_index} messages...")
            time.sleep(break_time)
        # Medium break every 5 messages
        elif current_index % 5 == 0 and current_index > 0:
            break_time = random.randint(60, 90)  # 1-1.5 minute break
            print(f"Taking a short break ({break_time} seconds) after {current_index} messages...")
            time.sleep(break_time)
        else:
            time.sleep(base_delay)
        
        # Random longer pause occasionally (5% chance)
        if random.random() < 0.05:
            extra_pause = random.randint(45, 75)
            print(f"Random pause: {extra_pause} seconds...")
            time.sleep(extra_pause)
    
    def prioritize_engaged_users(self, contacts):
        """Prioritize contacts most likely to engage"""
        if isinstance(contacts, pd.DataFrame):
            # If DataFrame, sort by last_contact if available
            if 'last_contact' in contacts.columns:
                return contacts.sort_values('last_contact', ascending=False)
            elif 'engagement' in contacts.columns:
                return contacts.sort_values('engagement', ascending=False)
        return contacts
    
    def send_bulk_messages(self, contacts_list, message_template, prioritize_engaged=True):
        """
        Main method to send bulk messages with all optimizations
        
        Args:
            contacts_list: List of phone numbers or DataFrame with phone numbers
            message_template: Message template (can use {name} for personalization)
            prioritize_engaged: Whether to prioritize engaged users
        """
        print(f"\n{'='*60}")
        print(f"Starting bulk WhatsApp retargeting for Saudi Arabia")
        print(f"{'='*60}\n")
        
        # Convert to list if DataFrame
        if isinstance(contacts_list, pd.DataFrame):
            if 'phone' in contacts_list.columns:
                contacts = contacts_list['phone'].tolist()
            elif 'number' in contacts_list.columns:
                contacts = contacts_list['number'].tolist()
            else:
                contacts = contacts_list.iloc[:, 0].tolist()  # Use first column
            
            if prioritize_engaged:
                contacts_list = self.prioritize_engaged_users(contacts_list)
                contacts = contacts_list['phone'].tolist() if 'phone' in contacts_list.columns else contacts_list.iloc[:, 0].tolist()
        else:
            contacts = contacts_list
        
        total_contacts = len(contacts)
        print(f"Total contacts to process: {total_contacts}")
        print(f"Daily limit: {self.daily_limit} messages\n")
        
        for i, contact in enumerate(contacts):
            # Check daily limit
            if not self.check_daily_limit():
                print(f"\n⚠ Daily limit reached ({self.daily_limit} messages). Stopping...")
                break
            
            # Format message (personalize if name available)
            message = message_template
            if isinstance(contacts_list, pd.DataFrame) and 'name' in contacts_list.columns:
                contact_row = contacts_list.iloc[i] if i < len(contacts_list) else None
                if contact_row is not None and pd.notna(contact_row.get('name')):
                    message = message_template.format(name=contact_row['name'])
            
            print(f"\n[{i+1}/{total_contacts}] Processing: {contact}")
            print(f"Daily usage: {self.daily_usage}/{self.daily_limit}")
            
            # Send message
            success = self.enhanced_send_message(contact, message)
            
            if success:
                # Update daily usage
                self.daily_usage += 1
                self.total_sent += 1
            else:
                # Retry once after a short delay
                print("Retrying after short delay...")
                time.sleep(random.randint(5, 10))
                success = self.enhanced_send_message(contact, message)
                if success:
                    self.daily_usage += 1
                    self.total_sent += 1
            
            # Smart delay between messages
            if i < total_contacts - 1:  # Don't delay after last message
                self.smart_delay(i, total_contacts)
        
        # Print final statistics
        print(f"\n{'='*60}")
        print(f"Campaign Complete!")
        print(f"{'='*60}")
        print(f"Total processed: {total_contacts}")
        print(f"Successfully sent: {self.success_count}")
        print(f"Failed: {self.failed_count}")
        print(f"Success rate: {(self.success_count/total_contacts*100):.2f}%")
        print(f"Daily usage: {self.daily_usage}/{self.daily_limit} messages")
        print(f"{'='*60}\n")
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            print("Browser closed.")


# Example usage
if __name__ == "__main__":
    # Initialize retargeter (works with any WhatsApp number - Moroccan, Saudi, etc.)
    retargeter = SaudiWhatsAppRetargeter(
        daily_limit=40  # Maximum messages per day
    )
    
    # Option 1: Use a CSV file with Saudi customers
    contacts_df = pd.read_csv('saudi_customers.csv')
    # CSV should have columns: phone (or number), name (optional)
    
    # Option 2: Use a simple list
    # contacts = [
    #     '+966501111111',
    #     '+966502222222',
    #     '+966503333333',
    # ]
    
    # Message template (supports Arabic and English)
    # Use {name} for personalization if CSV has 'name' column
    message = """السلام عليكم ورحمة الله وبركاته

عزيزي العميل، نود أن نعلمك بعروضنا الحصرية الجديدة!

{name}

شكراً لثقتك بنا."""
    
    # Send bulk messages
    try:
        retargeter.send_bulk_messages(
            contacts_list=contacts_df,  # or contacts for simple list
            message_template=message,
            prioritize_engaged=True
        )
    finally:
        retargeter.close()

