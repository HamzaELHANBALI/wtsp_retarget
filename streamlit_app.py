import streamlit as st
import pandas as pd
import time
import os
import re
import shutil
import json
from pathlib import Path
from datetime import datetime
import threading
from whatsapp_bot import WhatsAppBot
from clean_order_csv import clean_phone_number, clean_name, convert_arabic_numerals

# Page configuration
st.set_page_config(
    page_title="WhatsApp Bulk Messaging Bot",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #25D366;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions to load configuration from JSON files
def load_noura_prompt(prompt_file_name=None):
    """Load Noura prompt from JSON file, with fallback to default
    
    Args:
        prompt_file_name: Name of the prompt file to load (e.g., 'noura_prompt.json', 'noura_lighter_watch_bundle_prompt.json')
                         If None, tries default files in order: noura_lighter_watch_bundle_prompt.json, noura_electric_ashtray_prompt.json, noura_prompt.json
    """
    # Default priority: lighter watch bundle (new default), then electric ashtray, then tiger balm (old)
    default_files = ["noura_lighter_watch_bundle_prompt.json", "noura_electric_ashtray_prompt.json", "noura_prompt.json"]
    
    files_to_try = [prompt_file_name] if prompt_file_name else default_files
    
    for filename in files_to_try:
        try:
            prompt_file = Path(filename)
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    prompt = data.get('system_prompt', '')
                    if prompt:
                        return prompt
        except Exception as e:
            # Continue to next file if this one fails
            print(f"⚠️ Error loading {filename}: {e}")
            continue
    
    # If no file found or all failed, return None to use fallback
    return None

def list_available_prompt_files():
    """List all available prompt JSON files in the current directory"""
    prompt_files = []
    for file in Path(".").glob("noura*_prompt.json"):
        if file.is_file():
            prompt_files.append(file.name)
    # Sort to have lighter watch bundle first (default), then electric ashtray
    prompt_files.sort(key=lambda x: (
        x != "noura_lighter_watch_bundle_prompt.json",
        x != "noura_electric_ashtray_prompt.json",
        x
    ))
    return prompt_files

def load_initial_message():
    """Load initial message template from JSON file, with fallback to default"""
    try:
        message_file = Path("initial_message.json")
        if message_file.exists():
            with open(message_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                message = data.get('message_template', '')
                if message:
                    return message
        # If file doesn't exist or message is empty, return None to use fallback
        return None
    except Exception as e:
        # Silently fail and return None to use fallback
        print(f"⚠️ Error loading initial_message.json: {e}")
        return None

def load_followup_message():
    """Load follow-up message template from JSON file, with fallback to default"""
    try:
        message_file = Path("followup_message.json")
        if message_file.exists():
            with open(message_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                message = data.get('message_template', '')
                if message:
                    return message
        # If file doesn't exist or message is empty, return None to use fallback
        return None
    except Exception as e:
        # Silently fail and return None to use fallback
        print(f"⚠️ Error loading followup_message.json: {e}")
        return None

# Initialize session state
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'contacts_df' not in st.session_state:
    st.session_state.contacts_df = None
if 'message_stats' not in st.session_state:
    st.session_state.message_stats = {'sent': 0, 'failed': 0, 'total': 0}
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'monitored_contacts' not in st.session_state:
    st.session_state.monitored_contacts = []
if 'auto_monitoring_enabled' not in st.session_state:
    st.session_state.auto_monitoring_enabled = True
if 'selected_contacts' not in st.session_state:
    st.session_state.selected_contacts = []  # List of selected phone numbers for sending

# Helper functions
def auto_add_to_monitoring(phone):
    """Automatically add phone to monitoring list and clear conversation history"""
    if phone not in st.session_state.monitored_contacts:
        st.session_state.monitored_contacts.append(phone)
        # Also add to bot if exists
        if st.session_state.bot:
            if phone not in st.session_state.bot.monitored_contacts:
                st.session_state.bot.monitored_contacts.append(phone)
                # Clear conversation history when starting to monitor this contact
                st.session_state.bot.start_monitoring_contact(phone)

def check_and_respond_to_messages():
    """Check all monitored contacts for new messages and respond"""
    if not st.session_state.bot:
        print("⚠️  No bot instance found")
        return []

    print(f"\n{'='*60}")
    print(f"🔍 Checking {len(st.session_state.monitored_contacts)} monitored contact(s)...")
    print(f"{'='*60}")

    responses = []
    for phone in st.session_state.monitored_contacts:
        try:
            print(f"\n--- Checking {phone} ---")
            # Check for new messages
            new_msg = st.session_state.bot.get_new_messages(phone)

            if new_msg:
                print(f"✨ NEW MESSAGE DETECTED!")
                print(f"   From: {phone}")
                print(f"   Message: {new_msg[:100]}...")

                # Generate AI response
                print(f"📝 Generating AI response...")
                ai_response = st.session_state.bot.generate_ai_response(new_msg, phone)

                # Send response
                print(f"📤 Sending AI response...")
                send_success = st.session_state.bot.send_message(phone, ai_response)

                if send_success:
                    print(f"✅ Response sent successfully to {phone}")
                else:
                    print(f"❌ Failed to send response to {phone}")

                responses.append({
                    'phone': phone,
                    'customer_msg': new_msg,
                    'ai_response': ai_response,
                    'success': send_success,
                    'checked': True
                })
            else:
                print(f"ℹ️  No new messages from {phone}")
                # No new message found - still track that we checked
                responses.append({
                    'phone': phone,
                    'checked': True,
                    'no_new_message': True,
                    'success': False
                })

        except Exception as e:
            print(f"❌ ERROR checking/responding to {phone}: {e}")
            import traceback
            traceback.print_exc()
            responses.append({
                'phone': phone,
                'error': str(e),
                'success': False,
                'checked': True
            })

    print(f"\n{'='*60}")
    print(f"✅ Check complete. Processed {len(responses)} contact(s)")
    print(f"{'='*60}\n")
    return responses

# Helper functions (existing)
def validate_phone_number(phone):
    """Validate phone number format"""
    if pd.isna(phone):
        return False
    # Use the advanced cleaning function - if it returns a valid number, it's valid
    cleaned = clean_phone_number(phone)
    return cleaned is not None

def format_phone_number(phone, country_code="+966"):
    """Format phone number with country code using advanced cleaning"""
    return clean_phone_number(phone, country_code)

def parse_message_template(template, name="", phone="", custom_message=""):
    """Replace variables in message template"""
    message = template.replace("{name}", str(name))
    message = message.replace("{phone}", str(phone))
    message = message.replace("{custom_message}", str(custom_message))
    return message

# Main UI
st.markdown('<div class="main-header">📱 WhatsApp Bulk Messaging Bot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Send bulk messages and automate customer service with AI</div>', unsafe_allow_html=True)

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    # API Key - prioritize environment variable for security
    env_api_key = os.getenv("OPENAI_API_KEY", "")

    if env_api_key:
        # API key is set in environment - don't show input
        openai_api_key = env_api_key
        st.success("✅ OpenAI API Key loaded from environment")
        with st.expander("🔐 API Key Security"):
            st.info("API key is securely loaded from .env file")
            st.caption(f"Key starts with: {env_api_key[:7]}...")
    else:
        # No environment variable - show input (for local testing only)
        st.warning("⚠️ No API key found in .env file")
        openai_api_key = st.text_input(
            "OpenAI API Key (Local Testing Only)",
            type="password",
            help="⚠️ For deployment, use .env file instead!",
            placeholder="sk-..."
        )
        if openai_api_key:
            st.caption("⚠️ For production/deployment, add OPENAI_API_KEY to .env file")

    # Country Code
    country_code = st.selectbox(
        "Country Code",
        options=["+966", "+971", "+20", "+1", "+44","+212", "+33", "+49"],
        index=0,
        help="Select your country code for phone number formatting"
    )

    # System Prompt
    with st.expander("🤖 AI System Prompt"):
        # List available prompt files
        available_prompts = list_available_prompt_files()
        
        # Initialize selected_prompt_file in session state if not exists
        if 'selected_prompt_file' not in st.session_state:
            # Default to lighter watch bundle if available
            default_prompt_file = "noura_lighter_watch_bundle_prompt.json"
            if default_prompt_file in available_prompts:
                st.session_state.selected_prompt_file = default_prompt_file
            elif available_prompts:
                st.session_state.selected_prompt_file = available_prompts[0]
            else:
                st.session_state.selected_prompt_file = None
        
        # Prompt file selection
        if available_prompts:
            st.markdown("**Select Prompt File**")
            # Get display names (without extension, more readable)
            prompt_options = {f: f.replace("noura_", "").replace("_prompt.json", "").replace("_", " ").title() 
                            for f in available_prompts}
            # Find current index
            current_file = st.session_state.selected_prompt_file
            if current_file in available_prompts:
                default_index = available_prompts.index(current_file)
            else:
                default_index = 0 if available_prompts else 0
            
            selected_prompt_file = st.selectbox(
                "Prompt File",
                options=available_prompts,
                index=default_index,
                format_func=lambda x: prompt_options.get(x, x),
                help="Select which prompt file to use. Edit the JSON file to modify the prompt.",
                key="prompt_file_selector"
            )
            # Update session state
            st.session_state.selected_prompt_file = selected_prompt_file
            st.caption(f"📄 Using: {selected_prompt_file}")
        else:
            st.session_state.selected_prompt_file = None
            st.warning("⚠️ No prompt files found. Using default prompt.")
        
        # Load prompt from selected JSON file
        prompt_to_load = st.session_state.selected_prompt_file if st.session_state.selected_prompt_file else None
        default_prompt = load_noura_prompt(prompt_to_load)
        if default_prompt is None:
            # Fallback to hardcoded prompt if JSON file doesn't exist
            default_prompt = """
You are Noura, a sales consultant at Tiger Balm call center in Saudi Arabia. Your mission: BUILD TRUST → ANSWER QUESTIONS → CLOSE THE SALE.

## CORE RULES

### Message Style (CRITICAL)
- **2-4 sentences max** - customers get bored with long texts
- One main point per message
- Always finish sentences completely
- Conversational and direct, not formal
- Every message moves toward sale

### Must Do
1. **Answer sales questions concisely (1-2 sentences)**:
   - Product/payment/delivery/authenticity → brief answer + redirect
   - Example: "دفع عند الاستلام، 24-48 ساعة مجاني. وش مدينتك؟"

2. **Always redirect after answering**: "واضح؟ تبغى تطلب؟"

3. **Create urgency briefly**: "48 hours left" (mention once per message)

4. **Push 3-pack intelligently**: Present both, emphasize 3-pack, ONE upsell attempt

5. **Be persistent**: Don't give up after first "no" - try 5-6 strategies before stopping

6. **Confirm package BEFORE city**: "تبغى حبة وحدة أو 3 حبات؟"

7. **Close fast**: City received → [LEAD_CONFIRMED: Tiger Balm X-pack] → "تمام! بيتصلون اليوم 📞" → STOP

### Must Not Do
1. **Long messages** - no paragraphs, max 4 sentences
2. **Deep off-topic engagement** - brief response + redirect
3. **Multiple upsells** - ONE attempt only, accept rejection gracefully
4. **Over-explain after closing** - city received → confirm → STOP
5. **Give up early** - need 5-6 clear rejections before stopping
6. **Forget [LEAD_CONFIRMED] marker** - specify "1-pack" or "3-pack"

## PRODUCT & OFFERS

**Tiger Balm**: Natural herbal pain relief for muscles, back, joints, headaches, neck pain.

**LIMITED OFFERS (48 hours):**
- **1-pack**: 89 SAR
- **3-pack**: 149 SAR (Save 118 SAR - each jar 50 SAR) ⭐

**Payment**: Cash on delivery, 24-48h free delivery, 100% return guarantee.

## KEY RESPONSES

### Identity
**AR**: "أنا نورة من مركز اتصالات التايجر بالم 😊 فيه شي تبغى تعرفه؟"
**EN**: "I'm Noura from Tiger Balm call center 😊 What would you like to know?"

### Present Offers
**AR**: "عندنا: 1️⃣ حبة → 89 ريال | 2️⃣ 3 حبات → 149 ريال (توفر 118!)
90% يختارون الـ3 👌 أيش تفضل؟"
**EN**: "We have: 1️⃣ Single → 89 SAR | 2️⃣ 3-pack → 149 SAR (save 118!)
90% choose 3-pack 👌 Which one?"

### Upsell (1-pack → 3-pack, ONE TIME ONLY)
**AR**: "تمام! بس لو عجبك بترجع تطلب = 178 ريال. الـ3 الحين = 149 ريال فقط (توفر 29!)
دايم موجود بالبيت. 90% يختارون الـ3 لأنها أذكى 💡 ما تبغى تعيد النظر؟"
**EN**: "Okay! But if you reorder later = 178 SAR. 3-pack now = only 149 SAR (save 29!)
Always have it home. 90% choose 3-pack - smarter 💡 Reconsider?"

**If rejected**: "ماشي، احترم قرارك! 😊 حبة وحدة ✅ وش مدينتك؟"

### Authenticity
**AR**: "✅ مستورد أصلي (رقم تسلسل) ✅ دفع عند الاستلام—تشوف قبل ✅ ضمان استرجاع 100%
صفر مخاطرة! 🛡️ مرتاح؟ وش مدينتك؟"

### Off-Topic Deflect
**AR**: "[Brief answer] 😊 بس عرض التايجر بالم ينتهي خلال 48 ساعة! عندك ألم تحتاج تعالجه؟"

## OBJECTION HANDLING (5-6 ATTEMPTS REQUIRED)

**Attempt 1 (First "no")**: Empathy + pain point
**AR**: "فاهمك! بس هل عندك أي ألم؟ التايجر بالم طبيعي 100%. العرض (149 ريال لـ3) ما بيتكرر—بعد 48 ساعة السعر 267! دفع عند الاستلام—صفر مخاطرة 💡"

**Attempt 2 (Second "no")**: FOMO
**AR**: "لو بكرة العرض انتهى ورجعت تطلب بـ267 ريال (زيادة 118)—هل راح تندم؟ 💭 كثير عملاء ندموا. خلني أحجزلك—لو ما احتجته لا تستلمه. ضمنت السعر 🔥 وش رأيك؟"

**Attempt 3 (Third "no")**: Risk reversal
**AR**: "دفع عند الاستلام = ما تدفع لين تشوف ✅ لو ما عجبك = ترجعه مجاناً ✅ العرض ينتهي خلال 48 ساعة = بعدها 267 ريال ⚠️
صفر مخاطرة + توفير 118 ريال. ما تبغى تضمن السعر؟ 💡"

**Attempt 4 (Fourth "no")**: Social proof + breakdown
**AR**: "500+ عميل طلبوا هالأسبوع. 90% قالوا 'ليش ما طلبت أول!'
149 ÷ 3 = 50 ريال للحبة | كل حبة تدوم 3-4 شهور = أقل من نص ريال يومياً
أقل من قهوة! 🤯 ما يستاهل تجربة؟ دفع عند الاستلام!"

**Attempt 5 (Fifth "no")**: Emotional appeal
**AR**: "فاهمك وأحترم رأيك 100%! 🙏 بس سؤال أخير: تخيل بعد شهر احتجت المنتج ودفعت 118 ريال زيادة—هل راح تندم؟ 💔
خلني أحجزلك (دفع عند الاستلام). لو ما احتجته لا تستلمه. ضمنت السعر. آخر محاولة—وش رأيك؟ 🙏"

**Attempt 6 (Only after 5-6 clear "no"s)**: Exit gracefully
**AR**: "تمام، احترم قرارك تماماً 🙏 إذا غيرت رأيك خلال 48 ساعة—العرض لسا شغال! بالتوفيق ❤️"

## CLOSING FLOW

1. Customer shows interest
2. **Confirm package** (if unclear): "تبغى حبة وحدة أو 3 حبات؟"
3. **Get city**: "وش مدينتك؟"
4. **Close immediately**: "[LEAD_CONFIRMED: Tiger Balm X-pack] تمام! بيتصلون اليوم 📞"
5. **STOP** - no extra explanation

## QUICK EXAMPLES

**Customer**: "Who are you?"
**Noura**: "أنا نورة من مركز اتصالات التايجر بالم 😊 شغلي مساعدة العملاء. فيه شي تبغى تعرفه؟"

**Customer**: "Is it original?"
**Noura**: "100% أصلي! ✅ رقم تسلسل ✅ دفع عند الاستلام—تشوف قبل ✅ ضمان استرجاع. صفر مخاطرة 🛡️ أي نوع ألم عندك؟"

**Customer**: "أبغاه"
**Noura**: "رهيب! 🎉 تبغى: 1️⃣ حبة (89) أو 2️⃣ 3 حبات (149—أوفر!)؟"

**Customer**: "الـ3"
**Noura**: "ممتاز! ✅ وش مدينتك؟"

**Customer**: "جدة"
**Noura**: "[LEAD_CONFIRMED: Tiger Balm 3-pack] تمام! بيتصلون اليوم 📞"

**Customer**: "حبة وحدة"
**Noura**: "تمام! لو عجبك بترجع تطلب = 178. الـ3 الحين = 149 (توفر 29!) 90% يختارونها 💡 تعيد النظر?"

**Customer**: "لا، حبة بس"
**Noura**: "ماشي، احترم قرارك! 😊 حبة ✅ وش مدينتك؟"

## TONE
**Arabic**: Warm, urgent, persistent. Use: "صراحة", "خلني", "وش رأيك", "تمام", "رهيب"
**English**: Friendly, conversational, urgent. Use: "Honestly...", "Look...", "What do you think?"
**Emojis**: 🐯 🔥 ✅ 💚 😊 👌 📞 💡 🤯 😔 ⚠️ 🙏

## CRITICAL REMINDERS
- Keep ALL messages 2-4 sentences max
- Answer sales questions fully but briefly
- Always redirect to sale after answering
- Try 5-6 persistence strategies before giving up
- One upsell attempt only - respect rejection
- Confirm package before asking city
- Add [LEAD_CONFIRMED] marker and STOP after city
- Stay in character as helpful, knowledgeable Noura
            """
        
        current_prompt_file = st.session_state.selected_prompt_file if 'selected_prompt_file' in st.session_state else None
        if current_prompt_file:
            st.caption(f"💡 Edit {current_prompt_file} to update this prompt. Changes take effect after reloading the page.")
        else:
            st.caption("💡 Create a prompt JSON file (e.g., noura_lighter_watch_bundle_prompt.json) to customize. Changes take effect after reloading.")
        
        system_prompt = st.text_area(
            "Customize AI Behavior",
            value=default_prompt.strip() if default_prompt else "",
            height=400,
            help=f"Define how the AI should behave when responding to customers. Edit {current_prompt_file if current_prompt_file else 'prompt JSON file'} to change the default."
        )
        
        # File upload option to import new prompt
        st.markdown("**📥 Import Prompt File (Optional)**")
        uploaded_prompt = st.file_uploader(
            "Upload a prompt JSON file",
            type=['json'],
            help="Upload a new prompt JSON file. It will be saved to the project directory.",
            key="prompt_uploader"
        )
        
        if uploaded_prompt is not None:
            try:
                # Read uploaded file
                content = uploaded_prompt.read().decode('utf-8')
                data = json.loads(content)
                
                # Validate it has system_prompt
                if 'system_prompt' in data:
                    # Save to project directory
                    uploaded_filename = uploaded_prompt.name
                    # Ensure it follows naming convention
                    if not uploaded_filename.endswith('_prompt.json'):
                        if uploaded_filename.endswith('.json'):
                            uploaded_filename = uploaded_filename.replace('.json', '_prompt.json')
                        else:
                            uploaded_filename = f"noura_{uploaded_filename}_prompt.json"
                    
                    save_path = Path(uploaded_filename)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    st.success(f"✅ Prompt file saved: {uploaded_filename}")
                    
                    # Update session state to use the new file
                    st.session_state.selected_prompt_file = uploaded_filename
                    st.info("🔄 Please reload the page to use the new prompt file.")
                    st.rerun()
                else:
                    st.error("❌ Invalid prompt file. Must contain 'system_prompt' key.")
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON file: {e}")
            except Exception as e:
                st.error(f"❌ Error importing prompt file: {e}")

    # Delay Settings
    with st.expander("⏱️ Rate Limiting"):
        st.info("WhatsApp limits automated messages. Use delays to avoid account bans.")
        message_delay = st.slider(
            "Delay between messages (seconds)",
            min_value=5,
            max_value=30,
            value=8,
            help="Recommended: 8-10 seconds"
        )
        max_messages_per_session = st.number_input(
            "Max messages per session",
            min_value=1,
            max_value=100,
            value=40,
            help="Recommended: 40-50 messages"
        )
    
    # Follow-up (Relance) Settings
    with st.expander("📬 Follow-up Messages (Relance)"):
        st.info("Automatically send follow-up messages to customers who didn't respond after a set time.")
        
        followup_enabled = st.checkbox(
            "Enable Follow-up Messages",
            value=True,
            help="Automatically send follow-up messages to customers who didn't respond"
        )
        
        if followup_enabled:
            followup_delay_minutes = st.slider(
                "Follow-up Delay (minutes)",
                min_value=15,
                max_value=1440,  # 24 hours
                value=60,
                step=15,
                help="How long to wait before sending a follow-up (e.g., 30 min, 60 min, 2 hours)"
            )
            
            # Convert to hours for display
            followup_delay_hours = followup_delay_minutes / 60
            if followup_delay_hours >= 1:
                st.caption(f"⏱️ Follow-up will be sent after {followup_delay_hours:.1f} hour(s)")
            else:
                st.caption(f"⏱️ Follow-up will be sent after {followup_delay_minutes} minute(s)")
            
            # Load follow-up message from JSON file
            default_followup = load_followup_message()
            if default_followup is None:
                # Fallback to hardcoded message if JSON file doesn't exist
                default_followup = """مرحباً {name}! 👋

نشكرك على وقتك. نود أن نتأكد أنك رأيت عرضنا على Tiger Balm.

هل لديك أي أسئلة؟ نحن هنا للمساعدة! 💬"""
            
            # Custom follow-up message
            st.markdown("**Custom Follow-up Message (Optional)**")
            st.caption("💡 Edit followup_message.json to update the default. Leave empty to use default from JSON.")
            custom_followup = st.text_area(
                "Follow-up Message Template",
                value="",
                height=100,
                placeholder=f"Leave empty to use default from followup_message.json:\n\n{default_followup[:100]}...",
                help="Custom message to send as follow-up. Leave empty to use default from followup_message.json. Use {name} and {phone} as placeholders."
            )
            
            if custom_followup:
                st.caption("✅ Custom follow-up message will be used")
            else:
                st.caption(f"ℹ️ Default follow-up message from followup_message.json will be used")
        else:
            followup_delay_minutes = 60  # Default value
            custom_followup = ""
            st.caption("❌ Follow-up messages are disabled")
        
        # Update bot settings if bot exists
        if st.session_state.bot:
            st.session_state.bot.followup_enabled = followup_enabled
            st.session_state.bot.followup_delay_minutes = followup_delay_minutes
            st.session_state.bot.followup_message_template = custom_followup if custom_followup else None

    st.divider()

    # Login Section
    st.header("🔐 WhatsApp Login")

    # Check if saved session exists
    profile_dir = Path("whatsapp_profile")
    has_saved_session = profile_dir.exists() and any(profile_dir.iterdir())

    if not st.session_state.logged_in:
        # Show session status
        if has_saved_session:
            st.info("💾 Saved WhatsApp session detected!")
            st.caption("You won't need to scan QR code again - click below to reconnect")
        else:
            st.caption("First time? You'll need to scan a QR code with your phone")

        if st.button("🚀 Initialize Bot & Login", type="primary"):
            spinner_text = "Reconnecting to saved session..." if has_saved_session else "Initializing bot... Please wait for QR code"
            with st.spinner(spinner_text):
                try:
                    # Initialize bot
                    st.session_state.bot = WhatsAppBot(
                        openai_api_key=openai_api_key if openai_api_key else None,
                        system_prompt=system_prompt,
                        headless=False,
                        contacts_df=st.session_state.contacts_df
                    )
                    st.session_state.logged_in = True
                    success_msg = "✅ Bot reconnected! Check the browser window." if has_saved_session else "✅ Bot initialized! You should see WhatsApp Web in a browser window."
                    st.success(success_msg)
                    if not has_saved_session:
                        st.info("📱 Scan the QR code with your phone to login")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to initialize bot: {str(e)}")
    else:
        st.success("✅ Bot is active")
        st.caption("🔄 If you refresh the page, just click 'Initialize Bot' again - your session is saved!")
        if st.button("🔌 Disconnect", type="secondary"):
            if st.session_state.bot:
                st.session_state.bot.close()
            st.session_state.bot = None
            st.session_state.logged_in = False
            st.session_state.monitoring = False
            st.rerun()

        # Option to clear saved session
        with st.expander("🗑️ Clear Saved Session"):
            st.warning("⚠️ This will delete your saved WhatsApp session. You'll need to scan QR code again next time.")
            if st.button("Clear Session Data", type="secondary"):
                if profile_dir.exists():
                    shutil.rmtree(profile_dir)
                    st.success("✅ Session data cleared. You'll need to scan QR code on next login.")
                    st.info("💡 Tip: Disconnect and reconnect to start fresh.")

    st.divider()

    # Statistics
    st.header("📊 Session Stats")
    if st.session_state.bot:
        stats = st.session_state.bot.get_stats()

        # Overview metrics
        st.metric("📤 Messages Sent", stats.get('messages_sent', 0))
        st.metric("❌ Failed", stats.get('messages_failed', 0))
        st.metric("✅ Success Rate", f"{stats.get('success_rate', 0):.0%}")

        st.divider()

        # Read receipt metrics
        st.caption("📬 Message Status:")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("✓✓ Delivered", stats.get('messages_delivered', 0))
        with col2:
            st.metric("✓✓ Read", stats.get('messages_read', 0))

        st.divider()

        # Other stats
        st.metric("🤖 AI Responses", stats.get('ai_responses', 0))
        st.metric("💬 Conversations", len(stats.get('conversation_history', {})))

# Main content area - Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Bulk Messaging", "🤖 AI Auto-Responder", "📊 Analytics", "🎯 Confirmed Leads", "❓ Help"])

# Tab 1: Bulk Messaging
with tab1:
    if not st.session_state.logged_in:
        st.warning("⚠️ Please initialize the bot and login to WhatsApp first (see sidebar)")
    else:
        # Test Message Section (collapsed by default)
        with st.expander("🧪 Test Message (Optional - Expand to test before bulk sending)", expanded=False):
            st.info("💡 **Tip:** Test with your own number first to verify everything works before sending to many contacts!")

            test_col1, test_col2 = st.columns([1, 1])

            with test_col1:
                test_phone = st.text_input(
                    "Phone Number",
                    placeholder="+966501234567 or 0501234567",
                    help="Enter a phone number to test. Can be your own number.",
                    key="test_phone"
                )

                test_name = st.text_input(
                    "Name (for testing {name} variable)",
                    value="Test User",
                    help="This will be used for the {name} variable in your message",
                    key="test_name"
                )

                # Load initial message from JSON file for test
                test_default_message = load_initial_message()
                if test_default_message is None:
                    # Fallback to hardcoded message if JSON file doesn't exist
                    test_default_message = """السلام عليكم {name} 👋

🐯 Tiger Balm الأصلي - عرض حصري محدود!

🔥 عرضين استثنائيين:
   1️⃣ حبة وحدة → 89 ريال
   2️⃣ عرض العائلة (3 حبات) → 149 ريال بس!

💡 يعني كل حبة بـ50 ريال (توفير 118 ريال!)

✨ مميزات الطلب:
✅ دفع عند الاستلام (COD)
✅ توصيل 24-48 ساعة لبابك
✅ منتج أصلي 100% مضمون

مناسب لـ:
• آلام الظهر والرقبة
• الصداع والشقيقة
• آلام العضلات والمفاصل

⚠️ العرض ينتهي قريباً - الكمية محدودة!

تبي تستفيد من العرض؟"""
                
                test_message = st.text_area(
                    "Test Message",
                    value=test_default_message,
                    height=150,
                    help="Write your test message. Use {name} to personalize. Edit initial_message.json to change the default.",
                    key="test_message"
                )

                # Info about auto-monitoring
                if openai_api_key:
                    st.info("ℹ️ **Auto-monitoring enabled:** This number will be automatically added to AI monitoring after sending.")
                else:
                    st.caption("💡 Add OpenAI API key to enable AI monitoring")

            with test_col2:
                st.markdown("**📎 Test Media Files**")
                st.caption("💡 Main media sent after customer responds. Second media (free product) sent immediately after.")
                
                test_media = st.file_uploader(
                    "📎 Main Media (Optional) - Sent after customer responds",
                    type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                    help="Upload main product media for testing (max 500MB)",
                    key="test_media"
                )

                # Save uploaded test main media
                test_media_path = None
                if test_media is not None:
                    try:
                        # Get file size in MB
                        file_size_mb = test_media.size / (1024 * 1024)

                        if file_size_mb > 500:
                            st.error(f"❌ File too large: {file_size_mb:.1f}MB. Max: 500MB")
                        else:
                            temp_dir = Path("temp_media")
                            temp_dir.mkdir(exist_ok=True)
                            test_media_path = temp_dir / f"test_{test_media.name}"

                            with st.spinner(f"Uploading {test_media.name} ({file_size_mb:.1f}MB)..."):
                                with open(test_media_path, "wb") as f:
                                    f.write(test_media.getbuffer())

                            st.success(f"✅ Main media ready: {test_media.name} ({file_size_mb:.1f}MB)")
                    except Exception as e:
                        st.error(f"❌ Error uploading media: {str(e)}")
                        st.info("💡 Try a smaller file or different format")
                        test_media_path = None
                
                # Second test media upload
                test_media_2 = st.file_uploader(
                    "🎁 Second Media - Free Product (Optional) - Sent after main media",
                    type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                    help="Upload free product media for testing (max 500MB)",
                    key="test_media_2"
                )

                # Save uploaded test second media
                test_media_path_2 = None
                if test_media_2 is not None:
                    try:
                        # Get file size in MB
                        file_size_mb_2 = test_media_2.size / (1024 * 1024)

                        if file_size_mb_2 > 500:
                            st.error(f"❌ File too large: {file_size_mb_2:.1f}MB. Max: 500MB")
                        else:
                            temp_dir = Path("temp_media")
                            temp_dir.mkdir(exist_ok=True)
                            test_media_path_2 = temp_dir / f"test_{test_media_2.name}"

                            with st.spinner(f"Uploading {test_media_2.name} ({file_size_mb_2:.1f}MB)..."):
                                with open(test_media_path_2, "wb") as f:
                                    f.write(test_media_2.getbuffer())

                            st.success(f"✅ Free product media ready: {test_media_2.name} ({file_size_mb_2:.1f}MB)")
                    except Exception as e:
                        st.error(f"❌ Error uploading second media: {str(e)}")
                        st.info("💡 Try a smaller file or different format")
                        test_media_path_2 = None

                # Preview
                st.markdown("**Message Preview:**")
                preview_msg = parse_message_template(test_message, test_name, test_phone, "")
                st.text_area("Preview", value=preview_msg, height=120, disabled=True, key="test_preview")

            # Send test button
            if st.button("🚀 Send Test Message", type="primary", key="send_test"):
                if not test_phone:
                    st.error("❌ Please enter a phone number")
                else:
                    # Validate and format phone number
                    formatted_phone = format_phone_number(test_phone, country_code)

                    if not formatted_phone:
                        st.error(f"❌ Invalid phone number: {test_phone}")
                        st.info("Try formats like: +966501234567, 0501234567, or 966501234567")
                    else:
                        st.info(f"📤 Sending test message to {formatted_phone}...")

                        try:
                            # Parse message with variables
                            final_message = parse_message_template(test_message, test_name, formatted_phone, "")

                            # Send message
                            success = st.session_state.bot.send_message(
                                phone=formatted_phone,
                                message=final_message,
                                media_path=str(test_media_path) if test_media_path else None,
                                media_path_2=str(test_media_path_2) if test_media_path_2 else None
                            )

                            if success:
                                st.success(f"✅ Test message sent successfully to {formatted_phone}!")
                                st.balloons()
                                st.info("📱 Check your WhatsApp to verify the message was received correctly.")

                                # Automatically add to monitoring (no checkbox needed)
                                auto_add_to_monitoring(formatted_phone)
                                st.success(f"🤖 Automatically added {formatted_phone} to AI monitoring!")
                                st.info("💡 Go to 'AI Auto-Responder' tab to check for responses")
                            else:
                                st.error("❌ Failed to send test message. Check the browser window for errors.")
                                st.warning("Common issues:\n- Phone number not on WhatsApp\n- Not logged in\n- Internet connection")

                        except Exception as e:
                            st.error(f"❌ Error sending test message: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())

        st.divider()

        # Bulk Messaging Section
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("📋 Upload Contacts")

            # CSV format selection
            csv_format = st.radio(
                "Select CSV Format:",
                options=["Standard Format (phone, name, custom_message)", "E-commerce Orders (auto-clean)"],
                help="Standard: phone, name, custom_message\nE-commerce: OrderDate, name, phone, address (auto-cleans Arabic numerals)"
            )

            # CSV Upload
            uploaded_file = st.file_uploader(
                "Upload CSV file",
                type=['csv'],
                help="Upload a CSV file - format will be auto-detected based on your selection above"
            )

            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file, encoding='utf-8-sig')

                    # Handle E-commerce order format
                    if "E-commerce Orders" in csv_format:
                        st.info("🔄 Auto-cleaning e-commerce order data...")

                        # Detect columns by position for e-commerce format
                        # Expected: OrderDate, (empty), name, phone, address, ...
                        col_names = list(df.columns)

                        if len(col_names) >= 5:
                            # Map columns by position
                            order_date_col = col_names[0]
                            name_col = col_names[2]
                            phone_col = col_names[3]
                            address_col = col_names[4]

                            # Create standardized DataFrame
                            cleaned_df = pd.DataFrame()
                            cleaned_df['name'] = df[name_col].apply(clean_name)
                            cleaned_df['phone'] = df[phone_col].apply(lambda x: clean_phone_number(x, country_code))
                            cleaned_df['address'] = df[address_col].fillna('')
                            cleaned_df['custom_message'] = ''

                            # Filter out invalid phones
                            initial_count = len(cleaned_df)
                            cleaned_df = cleaned_df[cleaned_df['phone'].notna()]
                            
                            # Reset index to prevent index-related serialization issues
                            cleaned_df = cleaned_df.reset_index(drop=True)
                            
                            # Ensure all columns are clean (convert to string for safety)
                            for col in cleaned_df.columns:
                                if cleaned_df[col].dtype == 'object':
                                    cleaned_df[col] = cleaned_df[col].astype(str).fillna('')

                            st.success(f"✅ Cleaned {initial_count} records → {len(cleaned_df)} valid contacts")
                            st.info(f"📍 Removed {initial_count - len(cleaned_df)} records with invalid phone numbers")

                            df = cleaned_df
                        else:
                            st.error("❌ E-commerce CSV format not recognized. Expected at least 5 columns.")
                            df = None

                    # Validate required columns for standard format
                    if df is not None:
                        required_cols = ['phone']
                        missing_cols = [col for col in required_cols if col not in df.columns]

                        if missing_cols:
                            st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                        else:
                            # Add name column if missing
                            if 'name' not in df.columns:
                                df['name'] = 'Customer'

                            # Add custom_message column if missing
                            if 'custom_message' not in df.columns:
                                df['custom_message'] = ''

                            # For standard format, validate and format phone numbers
                            if "Standard Format" in csv_format:
                                df['phone_valid'] = df['phone'].apply(validate_phone_number)
                                df['phone_formatted'] = df.apply(
                                    lambda row: format_phone_number(row['phone'], country_code) if row['phone_valid'] else row['phone'],
                                    axis=1
                                )
                            else:
                                # E-commerce format already cleaned
                                df['phone_valid'] = df['phone'].notna()
                                df['phone_formatted'] = df['phone']
                            
                            # Clean DataFrame to prevent serialization issues
                            # Reset index and ensure all object columns are strings
                            df = df.reset_index(drop=True)
                            for col in df.columns:
                                if df[col].dtype == 'object':
                                    df[col] = df[col].fillna('').astype(str)

                            st.session_state.contacts_df = df

                            # Update bot's contacts_df if bot is already initialized
                            if st.session_state.bot:
                                st.session_state.bot.contacts_df = df

                            # Initialize selected contacts with all valid contacts (all selected by default)
                            valid_contacts_df = df[df['phone_valid'] == True]
                            st.session_state.selected_contacts = valid_contacts_df['phone_formatted'].tolist()

                            # Show preview
                            st.success(f"✅ Loaded {len(df)} contacts")

                            valid_count = df['phone_valid'].sum()
                            invalid_count = len(df) - valid_count

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric("Valid Numbers", valid_count)
                            with col_b:
                                st.metric("Invalid Numbers", invalid_count)

                            if invalid_count > 0:
                                st.warning("⚠️ Some phone numbers are invalid and will be skipped")

                            # Preview table
                            display_cols = ['name', 'phone_formatted', 'phone_valid']
                            if 'address' in df.columns:
                                display_cols.insert(2, 'address')

                            # Safely display DataFrame with error handling
                            try:
                                display_data = df[display_cols].head(10).copy()
                                # Ensure all data is serializable
                                display_data = display_data.fillna('')
                                st.dataframe(
                                    display_data,
                                    use_container_width=True
                                )
                            except Exception as display_err:
                                st.warning(f"⚠️ Could not display DataFrame preview: {display_err}")
                                st.info("💡 The CSV file was loaded successfully, but preview display failed.")

                except Exception as e:
                    st.error(f"❌ Error reading CSV: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

            # Download sample template
            st.divider()
            st.subheader("📥 Download Template")
            sample_data = pd.DataFrame({
                'phone': ['+966501234567', '966501234568', '0501234569'],
                'name': ['Ahmed', 'Fatima', 'Mohammed'],
                'custom_message': ['Special offer for you!', '', 'Thanks for your support!']
            })
            try:
                csv = sample_data.to_csv(index=False, encoding='utf-8')
                st.download_button(
                    label="⬇️ Download Sample CSV",
                    data=csv,
                    file_name="contacts_template.csv",
                    mime="text/csv"
                )
            except Exception as csv_err:
                st.error(f"⚠️ Error creating sample CSV: {csv_err}")

        with col2:
            st.subheader("💬 Compose Message")

            # Load initial message from JSON file
            default_message = load_initial_message()
            if default_message is None:
                # Fallback to hardcoded message if JSON file doesn't exist
                default_message = """السلام عليكم {name} 👋

🐯 Tiger Balm الأصلي - عرض حصري محدود!

🔥 عرضين استثنائيين:
   1️⃣ حبة وحدة → 89 ريال
   2️⃣ عرض العائلة (3 حبات) → 149 ريال بس!

💡 يعني كل حبة بـ50 ريال (توفير 118 ريال!)

✨ مميزات الطلب:
✅ دفع عند الاستلام (COD)
✅ توصيل 24-48 ساعة لبابك
✅ منتج أصلي 100% مضمون

مناسب لـ:
• آلام الظهر والرقبة
• الصداع والشقيقة
• آلام العضلات والمفاصل

⚠️ العرض ينتهي قريباً - الكمية محدودة!

تبي تستفيد من العرض؟"""
            
            st.caption("💡 Edit initial_message.json to update this template. Changes take effect after reloading the page.")
            # Message template
            message_template = st.text_area(
                "Message Template",
                value=default_message,
                height=150,
                help="Use {name}, {phone}, {custom_message} as placeholders. Edit initial_message.json to change the default."
            )

            # Media upload - Main media (sent after customer responds)
            st.markdown("**📎 Media Files**")
            st.caption("💡 Main media will be sent when customer responds. Second media (free product) will be sent immediately after.")
            
            media_file = st.file_uploader(
                "📎 Main Media (Optional) - Sent after customer responds",
                type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                help="Upload main product media. This will be sent when the customer responds to your initial message (max 500MB)",
                key="main_media"
            )

            # Save uploaded main media temporarily
            media_path = None
            if media_file is not None:
                try:
                    # Get file size in MB
                    file_size_mb = media_file.size / (1024 * 1024)

                    if file_size_mb > 500:
                        st.error(f"❌ File too large: {file_size_mb:.1f}MB. Max: 500MB")
                    else:
                        # Save to temp location
                        temp_dir = Path("temp_media")
                        temp_dir.mkdir(exist_ok=True)
                        media_path = temp_dir / media_file.name

                        with st.spinner(f"Uploading {media_file.name} ({file_size_mb:.1f}MB)..."):
                            with open(media_path, "wb") as f:
                                f.write(media_file.getbuffer())

                        st.success(f"✅ Main media attached: {media_file.name} ({file_size_mb:.1f}MB)")
                except Exception as e:
                    st.error(f"❌ Error uploading media: {str(e)}")
                    st.info("💡 Try a smaller file or different format")
                    media_path = None
            
            # Second media upload - Free product (sent immediately after main media)
            media_file_2 = st.file_uploader(
                "🎁 Second Media - Free Product (Optional) - Sent after main media",
                type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                help="Upload free product media (e.g., electric ashtray). This will be sent immediately after the main media (max 500MB)",
                key="second_media"
            )

            # Save uploaded second media temporarily
            media_path_2 = None
            if media_file_2 is not None:
                try:
                    # Get file size in MB
                    file_size_mb_2 = media_file_2.size / (1024 * 1024)

                    if file_size_mb_2 > 500:
                        st.error(f"❌ File too large: {file_size_mb_2:.1f}MB. Max: 500MB")
                    else:
                        # Save to temp location
                        temp_dir = Path("temp_media")
                        temp_dir.mkdir(exist_ok=True)
                        media_path_2 = temp_dir / media_file_2.name

                        with st.spinner(f"Uploading {media_file_2.name} ({file_size_mb_2:.1f}MB)..."):
                            with open(media_path_2, "wb") as f:
                                f.write(media_file_2.getbuffer())

                        st.success(f"✅ Free product media attached: {media_file_2.name} ({file_size_mb_2:.1f}MB)")
                except Exception as e:
                    st.error(f"❌ Error uploading second media: {str(e)}")
                    st.info("💡 Try a smaller file or different format")
                    media_path_2 = None

            # Preview message
            with st.expander("👁️ Preview Message"):
                if st.session_state.contacts_df is not None and len(st.session_state.contacts_df) > 0:
                    first_contact = st.session_state.contacts_df.iloc[0]
                    preview = parse_message_template(
                        message_template,
                        first_contact.get('name', 'Customer'),
                        first_contact.get('phone_formatted', ''),
                        first_contact.get('custom_message', '')
                    )
                    st.text(preview)
                else:
                    preview = parse_message_template(message_template, "John Doe", "+966501234567", "Sample message")
                    st.text(preview)

            st.divider()

            # Contact Selection Section (Improved for large lists)
            contacts_to_send = pd.DataFrame()  # Initialize empty DataFrame
            
            if st.session_state.contacts_df is not None:
                valid_contacts = st.session_state.contacts_df[st.session_state.contacts_df['phone_valid'] == True].copy()
                
                if len(valid_contacts) > 0:
                    st.subheader("📋 Select Contacts to Send")
                    
                    # Initialize selected_contacts if empty (all selected by default)
                    if not st.session_state.selected_contacts or len(st.session_state.selected_contacts) == 0:
                        st.session_state.selected_contacts = valid_contacts['phone_formatted'].tolist()
                    
                    # Ensure selected_contacts only contains valid phone numbers
                    valid_phones = set(valid_contacts['phone_formatted'].tolist())
                    st.session_state.selected_contacts = [
                        phone for phone in st.session_state.selected_contacts 
                        if phone in valid_phones
                    ]
                    
                    # Add a 'selected' column to the dataframe for easier filtering
                    valid_contacts['selected'] = valid_contacts['phone_formatted'].isin(st.session_state.selected_contacts)
                    
                    # === FILTERING AND SEARCH SECTION ===
                    st.markdown("### 🔍 Filter & Search Contacts")
                    
                    filter_col1, filter_col2, filter_col3 = st.columns(3)
                    
                    with filter_col1:
                        # Search by name
                        search_name = st.text_input(
                            "🔎 Search by Name",
                            value="",
                            placeholder="Type name to search...",
                            help="Filter contacts by name"
                        )
                    
                    with filter_col2:
                        # Search by phone
                        search_phone = st.text_input(
                            "📱 Search by Phone",
                            value="",
                            placeholder="Type phone to search...",
                            help="Filter contacts by phone number"
                        )
                    
                    with filter_col3:
                        # Filter by selection status
                        filter_selection = st.selectbox(
                            "📊 Filter by Selection",
                            options=["All", "Selected Only", "Unselected Only"],
                            help="Show all, only selected, or only unselected contacts"
                        )
                    
                    # Store current filter state to detect changes
                    current_filters = f"{search_name}|{search_phone}|{filter_selection}"
                    if 'last_filters' not in st.session_state:
                        st.session_state.last_filters = ""
                    
                    # Reset page to 0 if filters changed
                    if st.session_state.last_filters != current_filters:
                        st.session_state.contact_page = 0
                        st.session_state.last_filters = current_filters
                    
                    # Apply filters
                    filtered_contacts = valid_contacts.copy()
                    
                    if search_name:
                        filtered_contacts = filtered_contacts[
                            filtered_contacts['name'].str.contains(search_name, case=False, na=False)
                        ]
                    
                    if search_phone:
                        filtered_contacts = filtered_contacts[
                            filtered_contacts['phone_formatted'].str.contains(search_phone, case=False, na=False)
                        ]
                    
                    if filter_selection == "Selected Only":
                        filtered_contacts = filtered_contacts[filtered_contacts['selected'] == True]
                    elif filter_selection == "Unselected Only":
                        filtered_contacts = filtered_contacts[filtered_contacts['selected'] == False]
                    
                    # Get filtered count
                    filtered_count = len(filtered_contacts)
                    
                    # Ensure page number is valid after filtering
                    if filtered_count > 0:
                        # Initialize items_per_page for max_page calculation (use default 100)
                        items_per_page_default = 100
                        max_page = (filtered_count - 1) // items_per_page_default
                        if st.session_state.contact_page > max_page:
                            st.session_state.contact_page = 0
                    
                    # === SELECTION SUMMARY ===
                    total_valid = len(valid_contacts)
                    total_selected = len(st.session_state.selected_contacts)
                    total_unselected = total_valid - total_selected
                    filtered_selected = filtered_contacts['selected'].sum() if filtered_count > 0 else 0
                    
                    col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                    with col_sum1:
                        st.metric("Total Valid", total_valid)
                    with col_sum2:
                        st.metric("Selected", total_selected, delta=f"{total_selected/total_valid*100:.1f}%")
                    with col_sum3:
                        st.metric("Unselected", total_unselected)
                    with col_sum4:
                        st.metric("Filtered Results", filtered_count)
                    
                    # === BULK ACTIONS ===
                    st.markdown("### ⚡ Bulk Actions")
                    action_col1, action_col2, action_col3, action_col4, action_col5 = st.columns(5)
                    
                    with action_col1:
                        if st.button("✅ Select All", use_container_width=True, help="Select all contacts (including filtered)"):
                            st.session_state.selected_contacts = valid_contacts['phone_formatted'].tolist()
                            st.rerun()
                    
                    with action_col2:
                        if st.button("✅ Select Filtered", use_container_width=True, help="Select all filtered contacts"):
                            filtered_phones = filtered_contacts['phone_formatted'].tolist()
                            st.session_state.selected_contacts = list(set(st.session_state.selected_contacts + filtered_phones))
                            st.rerun()
                    
                    with action_col3:
                        if st.button("❌ Deselect All", use_container_width=True, help="Deselect all contacts"):
                            st.session_state.selected_contacts = []
                            st.rerun()
                    
                    with action_col4:
                        if st.button("❌ Deselect Filtered", use_container_width=True, help="Deselect all filtered contacts"):
                            filtered_phones = set(filtered_contacts['phone_formatted'].tolist())
                            st.session_state.selected_contacts = [
                                phone for phone in st.session_state.selected_contacts 
                                if phone not in filtered_phones
                            ]
                            st.rerun()
                    
                    with action_col5:
                        if st.button("🔄 Reset to All", use_container_width=True, help="Reset: Select all contacts"):
                            st.session_state.selected_contacts = valid_contacts['phone_formatted'].tolist()
                            st.rerun()
                    
                    st.divider()
                    
                    # === PAGINATED CONTACT TABLE ===
                    if filtered_count > 0:
                        st.markdown(f"### 📋 Contacts ({filtered_count} shown)")
                        
                        # Pagination controls
                        items_per_page = st.slider(
                            "Contacts per page",
                            min_value=50,
                            max_value=500,
                            value=100,
                            step=50,
                            help="Number of contacts to display per page"
                        )
                        
                        # Initialize page number in session state
                        if 'contact_page' not in st.session_state:
                            st.session_state.contact_page = 0
                        
                        total_pages = (filtered_count - 1) // items_per_page + 1
                        current_page = st.session_state.contact_page
                        
                        # Page navigation
                        nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 2, 2, 1])
                        with nav_col1:
                            if st.button("⬅️ Previous", disabled=current_page == 0, use_container_width=True):
                                st.session_state.contact_page = max(0, current_page - 1)
                                st.rerun()
                        
                        with nav_col2:
                            page_input = st.number_input(
                                "Page number",
                                min_value=1,
                                max_value=total_pages,
                                value=current_page + 1,
                                key="page_input",
                                label_visibility="collapsed"
                            )
                            if page_input != current_page + 1:
                                st.session_state.contact_page = page_input - 1
                                st.rerun()
                        
                        with nav_col3:
                            st.caption(f"Page {current_page + 1} of {total_pages} ({filtered_count} total)")
                        
                        with nav_col4:
                            if st.button("Next ➡️", disabled=current_page >= total_pages - 1, use_container_width=True):
                                st.session_state.contact_page = min(total_pages - 1, current_page + 1)
                                st.rerun()
                        
                        # Get contacts for current page
                        start_idx = current_page * items_per_page
                        end_idx = min(start_idx + items_per_page, filtered_count)
                        page_contacts = filtered_contacts.iloc[start_idx:end_idx]
                        
                        # Display contacts with checkboxes in a more compact format
                        st.markdown("---")
                        
                        # Create a container for the contact list
                        contacts_container = st.container()
                        
                        with contacts_container:
                            # Display contacts in a compact table format
                            # Use st.dataframe with a custom selection column for better performance
                            
                            # Create a display dataframe with selection status
                            display_df = page_contacts[['name', 'phone_formatted']].copy()
                            display_df['selected'] = display_df['phone_formatted'].isin(st.session_state.selected_contacts)
                            display_df['select'] = False  # Placeholder for checkbox column
                            
                            # Display as a more compact format using st.columns for each row
                            # This is more performant than individual checkboxes for large lists
                            
                            # Show table header
                            header_col1, header_col2, header_col3 = st.columns([1, 4, 3])
                            with header_col1:
                                st.markdown("**Select**")
                            with header_col2:
                                st.markdown("**Name**")
                            with header_col3:
                                st.markdown("**Phone**")
                            
                            st.markdown("---")
                            
                            # Display contacts with checkboxes
                            for row_idx, (idx, contact) in enumerate(page_contacts.iterrows()):
                                phone = contact['phone_formatted']
                                name = contact.get('name', 'Customer') or 'Customer'
                                is_selected = phone in st.session_state.selected_contacts
                                
                                # Create a row
                                col_chk, col_name, col_phone = st.columns([1, 4, 3])
                                
                                with col_chk:
                                    # Unique checkbox key (use phone number directly, page and row for uniqueness)
                                    # Replace special characters in phone for valid key
                                    safe_phone = phone.replace('+', 'plus').replace('-', '_').replace(' ', '_')
                                    checkbox_key = f"contact_checkbox_{safe_phone}_p{current_page}_r{row_idx}"
                                    # Use contact name as label (hidden for cleaner UI, but required for accessibility)
                                    checkbox_label = f"Select {name}"
                                    checked = st.checkbox(
                                        checkbox_label,
                                        value=is_selected,
                                        key=checkbox_key,
                                        label_visibility="collapsed"
                                    )
                                    
                                    # Update selection immediately if changed
                                    if checked != is_selected:
                                        if checked:
                                            if phone not in st.session_state.selected_contacts:
                                                st.session_state.selected_contacts.append(phone)
                                        else:
                                            if phone in st.session_state.selected_contacts:
                                                st.session_state.selected_contacts.remove(phone)
                                        # Rerun to update UI
                                        st.rerun()
                                
                                with col_name:
                                    # Show name with visual indicator
                                    if is_selected:
                                        st.markdown(f"✅ **{name}**")
                                    else:
                                        st.markdown(name)
                                
                                with col_phone:
                                    st.text(phone)
                        
                        st.markdown("---")
                        
                        # Quick selection for current page
                        page_action_col1, page_action_col2 = st.columns(2)
                        with page_action_col1:
                            if st.button(f"✅ Select All on This Page ({len(page_contacts)} contacts)", use_container_width=True):
                                page_phones = page_contacts['phone_formatted'].tolist()
                                st.session_state.selected_contacts = list(set(st.session_state.selected_contacts + page_phones))
                                st.rerun()
                        
                        with page_action_col2:
                            if st.button(f"❌ Deselect All on This Page ({len(page_contacts)} contacts)", use_container_width=True):
                                page_phones = set(page_contacts['phone_formatted'].tolist())
                                st.session_state.selected_contacts = [
                                    phone for phone in st.session_state.selected_contacts 
                                    if phone not in page_phones
                                ]
                                st.rerun()
                    
                    else:
                        st.info("🔍 No contacts match your filters. Try adjusting your search criteria.")
                    
                    st.divider()
                    
                    # === FINAL SELECTION PROCESSING ===
                    # Filter contacts based on final selection
                    if len(st.session_state.selected_contacts) > 0:
                        contacts_to_send = valid_contacts[valid_contacts['phone_formatted'].isin(st.session_state.selected_contacts)]
                        
                        # Apply max messages per session limit
                        if len(contacts_to_send) > max_messages_per_session:
                            st.warning(f"⚠️ You have {len(contacts_to_send)} selected contacts, but max limit is {max_messages_per_session}. Only the first {max_messages_per_session} will be sent.")
                            contacts_to_send = contacts_to_send.head(max_messages_per_session)
                    else:
                        contacts_to_send = pd.DataFrame()  # Empty DataFrame
                        
                else:
                    st.warning("⚠️ No valid contacts found in the CSV file")

            # Send messages button
            if st.session_state.contacts_df is not None and len(contacts_to_send) > 0:
                if st.button(f"🚀 Send to {len(contacts_to_send)} Contacts", type="primary", disabled=len(contacts_to_send)==0):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.container()

                    # Set bulk sending flag to pause background monitoring
                    if st.session_state.bot:
                        st.session_state.bot.bulk_sending_active = True
                        print("🔄 Bulk sending started - background monitoring paused")

                    sent_count = 0
                    failed_count = 0

                    try:
                        for idx, contact in contacts_to_send.iterrows():
                            try:
                                # Update progress
                                progress = (sent_count + failed_count + 1) / len(contacts_to_send)
                                progress_bar.progress(progress)
                                status_text.text(f"Sending to {contact['name']} ({contact['phone_formatted']})...")

                                # Parse message
                                message = parse_message_template(
                                    message_template,
                                    contact['name'],
                                    contact['phone_formatted'],
                                    contact.get('custom_message', '')
                                )

                                # Send message
                                success = st.session_state.bot.send_message(
                                    phone=contact['phone_formatted'],
                                    message=message,
                                    media_path=str(media_path) if media_path else None,
                                    media_path_2=str(media_path_2) if media_path_2 else None
                                )

                                if success:
                                    sent_count += 1
                                    # Automatically add to monitoring
                                    auto_add_to_monitoring(contact['phone_formatted'])
                                    with results_container:
                                        st.success(f"✅ Sent to {contact['name']} ({contact['phone_formatted']})")
                                else:
                                    failed_count += 1
                                    with results_container:
                                        st.error(f"❌ Failed to send to {contact['name']} ({contact['phone_formatted']})")

                                # Delay between messages
                                if sent_count + failed_count < len(contacts_to_send):
                                    time.sleep(message_delay)

                            except Exception as e:
                                failed_count += 1
                                with results_container:
                                    st.error(f"❌ Error sending to {contact['name']}: {str(e)}")

                        # Final summary
                        progress_bar.progress(1.0)
                        status_text.text("✅ Bulk messaging complete!")

                        st.divider()
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Total Sent", sent_count)
                        with col_b:
                            st.metric("Failed", failed_count)
                        with col_c:
                            success_rate = (sent_count / len(contacts_to_send) * 100) if len(contacts_to_send) > 0 else 0
                            st.metric("Success Rate", f"{success_rate:.1f}%")

                        # Update session stats
                        st.session_state.message_stats['sent'] += sent_count
                        st.session_state.message_stats['failed'] += failed_count
                        st.session_state.message_stats['total'] += len(contacts_to_send)
                    finally:
                        # Always reset bulk sending flag, even if there was an error
                        if st.session_state.bot:
                            st.session_state.bot.bulk_sending_active = False
                            print("✅ Bulk sending finished - background monitoring resumed")
            elif st.session_state.contacts_df is not None:
                # Contacts loaded but none selected or no valid contacts
                if len(contacts_to_send) == 0:
                    st.info("📋 Select at least one contact to send messages")
            else:
                st.info("📋 Upload a CSV file to get started")

# Tab 2: AI Auto-Responder
with tab2:
    if not st.session_state.logged_in:
        st.warning("⚠️ Please initialize the bot and login to WhatsApp first (see sidebar)")
    else:
        st.subheader("🤖 AI-Powered Customer Service")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 📱 Monitored Contacts")

            # Contact management
            if st.session_state.contacts_df is not None:
                # Combine CSV contacts with session monitored contacts
                available_contacts = st.session_state.contacts_df['phone_formatted'].tolist()
                # Add any session monitored contacts that aren't in CSV
                for contact in st.session_state.monitored_contacts:
                    if contact not in available_contacts:
                        available_contacts.append(contact)

                monitored_contacts = st.multiselect(
                    "Select contacts to monitor",
                    options=available_contacts,
                    default=st.session_state.monitored_contacts,  # Pre-select from test section
                    help="Select which contacts the bot should monitor and respond to"
                )
            else:
                # No CSV uploaded, use session monitored contacts
                monitored_contacts = st.multiselect(
                    "Select contacts to monitor",
                    options=st.session_state.monitored_contacts,
                    default=st.session_state.monitored_contacts,
                    help="Select which contacts the bot should monitor and respond to"
                )
                if len(st.session_state.monitored_contacts) == 0:
                    st.info("💡 Tip: Send a test message with 'Add to AI monitoring' checked, or add contacts manually below")

            # Manual contact addition
            manual_phone = st.text_input(
                "Or add phone manually",
                placeholder="+966501234567",
                help="Enter a phone number to monitor"
            )

            if manual_phone and st.button("➕ Add Contact"):
                if validate_phone_number(manual_phone):
                    formatted = format_phone_number(manual_phone, country_code)
                    if formatted not in st.session_state.monitored_contacts:
                        st.session_state.monitored_contacts.append(formatted)
                        # Also add to bot and clear history if bot exists
                        if st.session_state.bot:
                            if formatted not in st.session_state.bot.monitored_contacts:
                                st.session_state.bot.monitored_contacts.append(formatted)
                                # Clear conversation history when starting to monitor this contact
                                st.session_state.bot.start_monitoring_contact(formatted)
                                # Start auto-monitoring if not already running
                                if not st.session_state.bot.auto_monitoring_active:
                                    st.session_state.bot.start_auto_monitoring()
                        st.success(f"✅ Added {formatted} to monitoring list")
                        st.info("🔄 Refresh the page to see it in the list above")
                    else:
                        st.info("Contact already in monitoring list")
                else:
                    st.error("❌ Invalid phone number")

            st.divider()

            # Auto-monitoring status
            st.markdown("### 🔄 Auto-Monitoring Status")
            if st.session_state.bot:
                col_status, col_control = st.columns([2, 1])
                with col_status:
                    if st.session_state.bot.auto_monitoring_active:
                        st.success(f"🟢 Auto-monitoring is ACTIVE (checking every {st.session_state.bot.monitoring_check_interval} seconds)")
                        st.caption(f"Monitoring {len(st.session_state.bot.monitored_contacts)} contact(s)")
                        
                        # Show stopped contacts if any
                        stopped_contacts = list(st.session_state.bot.monitoring_stopped_contacts)
                        if stopped_contacts:
                            st.warning(f"⚠️ Monitoring stopped for {len(stopped_contacts)} contact(s)")
                            with st.expander("View stopped contacts"):
                                for phone in stopped_contacts:
                                    st.text(f"  • {phone}")
                    else:
                        st.info("ℹ️ Auto-monitoring is not active. It will start automatically when you send messages to contacts.")
                
                with col_control:
                    st.write("")  # Spacing
                    st.write("")  # Spacing
                    if st.session_state.bot.auto_monitoring_active:
                        if st.button("🛑 Stop Auto-Monitoring", type="secondary", use_container_width=True):
                            st.session_state.bot.stop_auto_monitoring()
                            st.success("✅ Auto-monitoring stopped")
                            st.rerun()
                    else:
                        if st.button("▶️ Start Auto-Monitoring", type="primary", use_container_width=True, disabled=len(st.session_state.bot.monitored_contacts)==0):
                            if not openai_api_key:
                                st.error("❌ Please enter OpenAI API key in sidebar")
                            else:
                                st.session_state.bot.start_auto_monitoring()
                                st.success("✅ Auto-monitoring started")
                                st.rerun()
            
            st.divider()

            # Individual contact monitoring controls
            if st.session_state.bot and st.session_state.bot.monitored_contacts:
                st.markdown("### 🎛️ Control Individual Contacts")
                st.caption("Stop or resume monitoring for specific contacts")
                
                # Create columns for contact controls
                for phone in st.session_state.bot.monitored_contacts[:10]:  # Show first 10 to avoid UI clutter
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        is_stopped = st.session_state.bot.is_contact_monitoring_stopped(phone)
                        status_icon = "⏸️" if is_stopped else "▶️"
                        status_text = "STOPPED" if is_stopped else "ACTIVE"
                        st.text(f"{status_icon} {phone} - {status_text}")
                    with col_b:
                        if is_stopped:
                            if st.button("▶️ Resume", key=f"resume_{phone}"):
                                st.session_state.bot.resume_monitoring_contact(phone)
                                st.success(f"✅ Resumed monitoring for {phone}")
                                st.rerun()
                        else:
                            if st.button("⏸️ Stop", key=f"stop_{phone}"):
                                st.session_state.bot.stop_monitoring_contact(phone)
                                st.success(f"✅ Stopped monitoring for {phone}")
                                st.rerun()
                
                if len(st.session_state.bot.monitored_contacts) > 10:
                    st.caption(f"... and {len(st.session_state.bot.monitored_contacts) - 10} more contacts")
            
            st.divider()

            # Monitoring controls
            st.markdown("### ⚙️ Manual Monitoring Settings")

            check_interval = st.slider(
                "Check interval (seconds)",
                min_value=5,
                max_value=60,
                value=10,
                help="How often to check for new messages"
            )

            # Manual check button (works anytime)
            if st.button("🔍 Check for New Messages & Respond Now", type="primary", disabled=len(monitored_contacts)==0):
                if not openai_api_key:
                    st.error("❌ Please enter OpenAI API key in sidebar")
                else:
                    with st.spinner(f"Checking {len(monitored_contacts)} contacts for new messages..."):
                        # Update bot's monitored contacts and clear history for new ones
                        old_monitored = set(st.session_state.bot.monitored_contacts)
                        new_monitored = set(monitored_contacts)
                        newly_added = new_monitored - old_monitored
                        
                        # Clear history for newly added contacts
                        for phone in newly_added:
                            st.session_state.bot.start_monitoring_contact(phone)
                        
                        # Update bot's monitored contacts
                        st.session_state.bot.monitored_contacts = monitored_contacts
                        # Check and respond
                        responses = check_and_respond_to_messages()

                        if responses:
                            # Count actual new messages
                            new_messages_count = len([r for r in responses if r.get('success') and r.get('customer_msg')])
                            checked_count = len([r for r in responses if r.get('checked')])

                            if new_messages_count > 0:
                                st.success(f"✅ Checked {checked_count} contacts. Found {new_messages_count} new messages!")
                            else:
                                st.info(f"ℹ️ Checked {checked_count} contacts. No new messages found.")

                            # Display responses
                            for resp in responses:
                                if resp.get('success') and resp.get('customer_msg'):
                                    # Successfully responded to a new message
                                    with st.expander(f"✅ Responded to {resp['phone']}", expanded=True):
                                        st.markdown(f"**Customer:** {resp['customer_msg']}")
                                        st.markdown(f"**AI Response:** {resp['ai_response']}")
                                elif resp.get('no_new_message'):
                                    # Checked but no new message
                                    with st.expander(f"ℹ️ {resp['phone']} - No new messages"):
                                        st.info("Contact was checked but no new messages were found.")
                                        st.caption("💡 Make sure you reply to the bot's message in WhatsApp first!")
                                elif resp.get('error'):
                                    # Error occurred
                                    with st.expander(f"❌ Error with {resp['phone']}"):
                                        st.error(f"Error: {resp.get('error', 'Unknown error')}")
                        else:
                            st.info("ℹ️ No contacts to check.")

            st.caption("💡 Click the button above to manually check for messages and send AI responses.")

            st.divider()

            # Automatic monitoring (continuous) - Optional
            st.markdown("### 🔄 Auto-Refresh (Optional)")
            st.info("⚠️ Auto-refresh will reload the page periodically. Use 'Check Now' button above for one-time checks.")

            # Start/Stop monitoring
            if not st.session_state.monitoring:
                if st.button("▶️ Enable Auto-Refresh", type="secondary", disabled=len(monitored_contacts)==0):
                    if not openai_api_key:
                        st.error("❌ Please enter OpenAI API key in sidebar")
                    else:
                        st.session_state.monitoring = True
                        st.session_state.bot.monitored_contacts = monitored_contacts
                        st.success("✅ Auto-refresh enabled!")
                        st.info(f"Page will auto-refresh every {check_interval} seconds to check for new messages.")
                        st.rerun()
            else:
                if st.button("⏸️ Disable Auto-Refresh", type="secondary"):
                    st.session_state.monitoring = False
                    st.info("Auto-refresh disabled")
                    st.rerun()

        with col2:
            st.markdown("### 💬 Live Activity")

            if st.session_state.monitoring:
                st.info(f"🟢 Auto-refresh enabled (every {check_interval}s)")

                # Auto-check for messages when monitoring is enabled
                with st.spinner("Checking for new messages..."):
                    # Update bot's monitored contacts and clear history for new ones
                    old_monitored = set(st.session_state.bot.monitored_contacts)
                    new_monitored = set(monitored_contacts)
                    newly_added = new_monitored - old_monitored
                    
                    # Clear history for newly added contacts
                    for phone in newly_added:
                        st.session_state.bot.start_monitoring_contact(phone)
                    
                    # Update bot's monitored contacts
                    st.session_state.bot.monitored_contacts = monitored_contacts
                    # Check and respond automatically
                    responses = check_and_respond_to_messages()

                    if responses:
                        # Count actual new messages
                        new_messages_count = len([r for r in responses if r.get('success') and r.get('customer_msg')])
                        checked_count = len([r for r in responses if r.get('checked')])

                        if new_messages_count > 0:
                            st.success(f"✅ Found {new_messages_count} new messages!")
                        else:
                            st.info(f"ℹ️ Checked {checked_count} contacts. No new messages yet.")

                        # Display responses
                        for resp in responses:
                            if resp.get('success') and resp.get('customer_msg'):
                                with st.expander(f"✅ Responded to {resp['phone']}", expanded=True):
                                    st.markdown(f"**Customer:** {resp['customer_msg']}")
                                    st.markdown(f"**AI Response:** {resp['ai_response']}")
                            elif resp.get('error'):
                                with st.expander(f"❌ Error with {resp['phone']}"):
                                    st.error(f"Error: {resp.get('error', 'Unknown error')}")
                    else:
                        st.info("ℹ️ No contacts to check.")

                # Display conversation history
                st.markdown("#### Recent Conversations")
                if st.session_state.bot:
                    stats = st.session_state.bot.get_stats()
                    conv_history = stats.get('conversation_history', {})

                    if conv_history:
                        for phone, messages in list(conv_history.items())[-5:]:  # Show last 5 conversations
                            with st.expander(f"💬 {phone}"):
                                for msg in messages[-5:]:  # Show last 5 messages per contact
                                    role = msg.get('role', 'user')
                                    content = msg.get('content', '')
                                    if role == 'user':
                                        st.markdown(f"**Customer:** {content}")
                                    else:
                                        st.markdown(f"**AI:** {content}")
                    else:
                        st.info("No conversations yet.")

                # Auto-refresh countdown
                st.caption(f"🔄 Page will auto-refresh in {check_interval} seconds...")
                time.sleep(check_interval)
                st.rerun()
            else:
                # Manual refresh option when not monitoring
                st.info("👆 Use 'Check for New Messages & Respond Now' button to manually check for messages")

                # Display conversation history
                st.markdown("#### Recent Conversations")
                if st.session_state.bot:
                    stats = st.session_state.bot.get_stats()
                    conv_history = stats.get('conversation_history', {})

                    if conv_history:
                        for phone, messages in list(conv_history.items())[-5:]:  # Show last 5 conversations
                            with st.expander(f"💬 {phone}"):
                                for msg in messages[-5:]:  # Show last 5 messages per contact
                                    role = msg.get('role', 'user')
                                    content = msg.get('content', '')
                                    if role == 'user':
                                        st.markdown(f"**Customer:** {content}")
                                    else:
                                        st.markdown(f"**AI:** {content}")
                    else:
                        st.info("💡 Send messages to contacts, then use the 'Check Now' button to test AI responses.")

                # Manual refresh button
                if st.button("🔄 Refresh View"):
                    st.rerun()

# Tab 3: Analytics
with tab3:
    st.subheader("📊 Analytics Dashboard")

    if st.session_state.bot:
        stats = st.session_state.bot.get_stats()

        # Key metrics - Row 1
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📤 Messages Sent", stats.get('messages_sent', 0))
        with col2:
            st.metric("❌ Messages Failed", stats.get('messages_failed', 0))
        with col3:
            success_rate = stats.get('success_rate', 0)
            st.metric("✅ Success Rate", f"{success_rate:.0%}")
            st.caption("(Sent / Total Attempts)")
        with col4:
            st.metric("🤖 AI Responses", stats.get('ai_responses', 0))

        # Read Receipt Stats - Row 2
        st.markdown("### 📬 Message Status")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sent = stats.get('messages_sent', 0)
            st.metric("📨 Total Sent", sent)
        with col2:
            delivered = stats.get('messages_delivered', 0)
            st.metric("✓✓ Delivered", delivered)
            if sent > 0:
                st.caption(f"{(delivered/sent*100):.1f}% of sent")
        with col3:
            read = stats.get('messages_read', 0)
            st.metric("✓✓ Read (Blue Checks)", read)
            if sent > 0:
                st.caption(f"{(read/sent*100):.1f}% of sent")
        with col4:
            conversations = len(stats.get('conversation_history', {}))
            st.metric("💬 Conversations", conversations)

        st.divider()

        # Session stats
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Session Statistics")
            st.metric("Total Sent (This Session)", st.session_state.message_stats['sent'])
            st.metric("Total Failed (This Session)", st.session_state.message_stats['failed'])
            if st.session_state.message_stats['total'] > 0:
                session_rate = (st.session_state.message_stats['sent'] / st.session_state.message_stats['total'] * 100)
                st.metric("Session Success Rate", f"{session_rate:.1f}%")

        with col2:
            st.markdown("### Conversation History")
            conv_history = stats.get('conversation_history', {})
            if conv_history:
                for phone in conv_history:
                    msg_count = len(conv_history[phone])
                    st.text(f"📱 {phone}: {msg_count} messages")
            else:
                st.info("No conversations yet")
    else:
        st.info("Initialize the bot to see analytics")

# Tab 4: Help
# Tab 4: Confirmed Leads
with tab4:
    st.subheader("🎯 Confirmed Leads")

    if not st.session_state.logged_in:
        st.warning("⚠️ Please initialize the bot first (see sidebar)")
    else:
        st.markdown("""
        This section shows all customers who have confirmed their purchase during the conversation.
        The AI automatically detects when customers provide their full order details and saves them here.
        """)

        # Get leads from bot
        leads = st.session_state.bot.get_leads()

        if len(leads) == 0:
            st.info("📭 No confirmed leads yet. When customers confirm their orders, they will appear here automatically.")
        else:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Leads", len(leads))
            with col2:
                pending_count = sum(1 for lead in leads if lead['status'] == 'pending')
                st.metric("Pending", pending_count)
            with col3:
                contacted_count = sum(1 for lead in leads if lead['status'] == 'contacted')
                st.metric("Contacted", contacted_count)
            with col4:
                converted_count = sum(1 for lead in leads if lead['status'] == 'converted')
                st.metric("Converted", converted_count)

            st.divider()

            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                filter_status = st.selectbox(
                    "Filter by Status",
                    options=["All", "pending", "contacted", "converted", "rejected"],
                    index=0
                )
            with col2:
                search_query = st.text_input("Search by phone or product", placeholder="+966...")

            # Filter leads
            filtered_leads = leads
            if filter_status != "All":
                filtered_leads = [lead for lead in filtered_leads if lead['status'] == filter_status]
            if search_query:
                filtered_leads = [
                    lead for lead in filtered_leads
                    if search_query.lower() in lead['phone'].lower() or search_query.lower() in lead['product_confirmed'].lower()
                ]

            st.caption(f"Showing {len(filtered_leads)} of {len(leads)} leads")

            # Display leads table
            if len(filtered_leads) > 0:
                # Convert to DataFrame for better display
                import pandas as pd
                try:
                    df_leads = pd.DataFrame(filtered_leads)
                    # Reset index to prevent index-related serialization issues
                    df_leads = df_leads.reset_index(drop=True)
                    
                    # Clean DataFrame to prevent serialization issues
                    # Fill NaN values and ensure all object columns are strings
                    for col in df_leads.columns:
                        if df_leads[col].dtype == 'object':
                            df_leads[col] = df_leads[col].fillna('').astype(str)
                        else:
                            df_leads[col] = df_leads[col].fillna('')
                    
                    # Display table with error handling to prevent recursion errors
                    try:
                        st.dataframe(
                            df_leads,
                            use_container_width=True,
                            hide_index=True
                        )
                    except RecursionError:
                        st.error("⚠️ Recursion error displaying table. This is a known pandas/Streamlit issue.")
                        st.info("💡 Try filtering the leads or use the download button instead.")
                        # Show simple text table instead
                        st.markdown("**Leads List (simple view):**")
                        for lead in filtered_leads[:50]:  # Show first 50
                            st.text(f"{lead.get('phone', 'N/A')} - {lead.get('product_confirmed', 'N/A')} - {lead.get('status', 'N/A')}")
                        if len(filtered_leads) > 50:
                            st.caption(f"... and {len(filtered_leads) - 50} more leads")
                    except Exception as display_err:
                        st.error(f"⚠️ Error displaying leads table: {display_err}")
                        st.info("💡 Leads data is loaded, but table display failed. Try downloading the CSV instead.")
                except RecursionError:
                    st.error("⚠️ Recursion error creating DataFrame. There may be an issue with the leads data.")
                    st.info("💡 Try clearing the leads file or checking for corrupted data.")
                    # Prevent infinite rerun
                    import sys
                    sys.setrecursionlimit(1000)  # Reset recursion limit
                except Exception as df_err:
                    st.error(f"⚠️ Error creating DataFrame: {df_err}")
                    st.info("💡 There might be an issue with the leads data structure.")

                st.divider()

                # Update status section
                st.markdown("### 📝 Update Lead Status")
                col1, col2, col3 = st.columns(3)

                with col1:
                    selected_phone = st.selectbox(
                        "Select Lead",
                        options=[lead['phone'] for lead in filtered_leads],
                        format_func=lambda x: f"{x} - {next((l['product_confirmed'] for l in filtered_leads if l['phone'] == x), '')}"
                    )

                with col2:
                    new_status = st.selectbox(
                        "New Status",
                        options=["pending", "contacted", "converted", "rejected"]
                    )

                with col3:
                    st.write("")  # Spacing
                    st.write("")  # Spacing
                    if st.button("Update Status", type="primary"):
                        st.session_state.bot.update_lead_status(selected_phone, new_status)
                        st.success(f"✅ Updated {selected_phone} to {new_status}")
                        st.rerun()

                st.divider()

                # Download section
                st.markdown("### 📥 Export Leads")
                st.markdown("Download the confirmed leads CSV file to share with your call center team.")

                import io

                # Create CSV string with error handling (use filtered_leads directly to avoid DataFrame issues)
                csv_string = ""
                try:
                    # Use Python's csv module instead of pandas to avoid recursion issues
                    import csv as csv_module
                    csv_buffer = io.StringIO()
                    if filtered_leads:
                        # Get fieldnames from first lead
                        fieldnames = list(filtered_leads[0].keys())
                        writer = csv_module.DictWriter(csv_buffer, fieldnames=fieldnames)
                        writer.writeheader()
                        for lead in filtered_leads:
                            # Ensure all values are strings and handle None values
                            clean_lead = {k: str(v) if v is not None else '' for k, v in lead.items()}
                            writer.writerow(clean_lead)
                    csv_string = csv_buffer.getvalue()
                except RecursionError:
                    st.error("⚠️ Recursion error creating CSV export. This is a pandas/Streamlit compatibility issue.")
                    st.info("💡 The leads data is loaded, but CSV export failed due to a technical issue.")
                    csv_string = ""  # Empty CSV if export fails
                except Exception as csv_err:
                    st.error(f"⚠️ Error creating CSV export: {csv_err}")
                    csv_string = ""  # Empty CSV if export fails

                st.download_button(
                    label="⬇️ Download Leads CSV",
                    data=csv_string,
                    file_name=f"confirmed_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    type="primary"
                )

                # Show individual lead details
                st.divider()
                st.markdown("### 🔍 Lead Details")

                selected_lead_phone = st.selectbox(
                    "View full details for:",
                    options=[lead['phone'] for lead in filtered_leads],
                    format_func=lambda x: f"{x} - {next((l['product_confirmed'] for l in filtered_leads if l['phone'] == x), '')}",
                    key="lead_details_selector"
                )

                selected_lead = next((lead for lead in filtered_leads if lead['phone'] == selected_lead_phone), None)

                if selected_lead:
                    st.markdown(f"**Phone:** {selected_lead['phone']}")
                    st.markdown(f"**Name:** {selected_lead['name']}")
                    st.markdown(f"**Product Confirmed:** {selected_lead['product_confirmed']}")
                    st.markdown(f"**Status:** {selected_lead['status']}")
                    st.markdown(f"**Timestamp:** {selected_lead['timestamp']}")
                    st.markdown(f"**Conversation Summary:** {selected_lead['conversation_summary']}")

                    # Show full conversation history if available
                    if selected_lead_phone in st.session_state.bot.conversations:
                        st.markdown("**Full Conversation:**")
                        conversation = st.session_state.bot.conversations[selected_lead_phone]
                        for msg in conversation:
                            role = "👤 Customer" if msg['role'] == 'user' else "🤖 AI"
                            st.markdown(f"**{role}:** {msg['content']}")
            else:
                st.info("No leads match your filters.")

# Tab 5: Help
with tab5:
    st.subheader("❓ Help & Documentation")

    st.markdown("""
    ## 🚀 Getting Started

    ### 1. Initial Setup
    1. Enter your **OpenAI API Key** in the sidebar
    2. Select your **Country Code** (default: Saudi Arabia +966)
    3. Click **Initialize Bot & Login**
    4. Scan the QR code with WhatsApp on your phone

    ### 2. Bulk Messaging
    1. Go to the **Bulk Messaging** tab
    2. Upload a CSV file with your contacts (or download the template)
    3. Compose your message (use {name}, {phone}, {custom_message} as placeholders)
    4. Optionally attach media (images/videos)
    5. Click **Send** and monitor the progress

    ### 3. AI Auto-Responder
    1. Go to the **AI Auto-Responder** tab
    2. Select contacts to monitor (or add manually)
    3. Adjust the check interval
    4. Click **Start Monitoring**
    5. The bot will automatically respond to incoming messages using AI

    ## 📋 CSV Format

    Your CSV file should have these columns:
    - **phone** (required): Phone number with or without country code
    - **name** (optional): Contact name (defaults to "Customer")
    - **custom_message** (optional): Custom message per contact

    Example:
    ```
    phone,name,custom_message
    +966501234567,Ahmed,Special discount for you!
    0501234568,Fatima,
    966501234569,Mohammed,Thank you for your loyalty!
    ```

    ## ⚠️ Important Warnings

    ### Rate Limiting
    - **Max 40-50 messages per day** recommended
    - **Use 8-10 second delays** between messages
    - **Risk of account ban** if you send too many messages

    ### Legal Compliance
    - Only message people who **consented**
    - Comply with **GDPR** and local laws
    - Don't send spam
    - Include **opt-out instructions**

    ### Terms of Service
    - Using automation may **violate WhatsApp ToS**
    - Use at your own risk
    - Account may be banned

    ## 🔧 Troubleshooting

    ### Bot won't login
    - Make sure WhatsApp Web is not already open in another browser
    - Delete the `whatsapp_profile` folder and try again
    - Check your internet connection

    ### Messages not sending
    - Verify phone numbers are in correct format
    - Check if you're logged in to WhatsApp
    - Reduce sending speed (increase delay)

    ### AI not responding
    - Make sure OpenAI API key is correct
    - Check if you have API credits
    - Verify the system prompt is appropriate

    ## 📧 Support

    For issues and questions, please check the README.md file or create an issue on GitHub.

    ## 🎯 Tips for Best Results

    1. **Test first**: Send to 1-2 contacts before bulk sending
    2. **Use delays**: Respect WhatsApp's rate limits
    3. **Personalize**: Use {name} to make messages feel personal
    4. **Monitor carefully**: Watch the AI responses to ensure quality
    5. **Stay legal**: Always get consent before messaging
    """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>⚡ Powered by OpenAI GPT-4 | Built with Streamlit & Selenium</p>
    <p>⚠️ Use responsibly and comply with WhatsApp Terms of Service</p>
</div>
""", unsafe_allow_html=True)
