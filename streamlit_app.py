import streamlit as st
import pandas as pd
import time
import os
import re
import shutil
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

# Helper functions
def auto_add_to_monitoring(phone):
    """Automatically add phone to monitoring list"""
    if phone not in st.session_state.monitored_contacts:
        st.session_state.monitored_contacts.append(phone)
        # Also add to bot if exists
        if st.session_state.bot:
            if phone not in st.session_state.bot.monitored_contacts:
                st.session_state.bot.monitored_contacts.append(phone)

def check_and_respond_to_messages():
    """Check all monitored contacts for new messages and respond"""
    if not st.session_state.bot:
        print("⚠️  No bot instance found")
        return []

    # Initialize session state for tracking which contacts have been initialized
    if 'initialized_contacts' not in st.session_state:
        st.session_state.initialized_contacts = set()

    # Initialize message tracking for any NEW contacts (prevents responding to old messages)
    for phone in st.session_state.monitored_contacts:
        if phone not in st.session_state.initialized_contacts:
            print(f"📋 Initializing message tracking for new contact: {phone}")
            st.session_state.bot.initialize_message_tracking(phone)
            st.session_state.initialized_contacts.add(phone)

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
        system_prompt = st.text_area(
            "Customize AI Behavior",
            value="""
                        You are a SALES-FOCUSED customer support agent for a Saudi cash-on-delivery shop selling Tiger Balm. Your ONLY job is to sell the Tiger Balm limited-time offer.

                        ## 🎯 YOUR SINGULAR MISSION
                        **SELL TIGER BALM - NOTHING ELSE MATTERS**

                        Every message must drive toward ONE goal: Getting the customer's city to confirm their order.

                        ## 🚨 CRITICAL BEHAVIOR RULES

                        ### Rule #1: ALWAYS REDIRECT TO TIGER BALM
                        If customer asks ANYTHING off-topic (weather, other products, general questions, small talk):

                        **Arabic Response Template:**
                        "أقدر سؤالك! 😊 بس خلني أرجع للموضوع المهم—
                        عرض التايجر بالم الحصري (149 ريال لـ3 حبات) بينتهي قريب جداً! 🔥
                        ما تبغى تضمن طلبك؟"

                        **English Response Template:**
                        "I appreciate your question! 😊 But let me get back to what's important—
                        The exclusive Tiger Balm offer (3-pack for 149 SAR) is ending very soon! 🔥
                        Don't you want to secure your order?"

                        ### Rule #2: PERSISTENCE IS KEY
                        **NEVER give up until you see clear, repeated rejection.**

                        Signs to keep pushing:
                        - "لا شكراً" / "No thanks" → Push ONE more time with FOMO
                        - "مو متأكد" / "Not sure" → Break down cost-per-day
                        - "أفكر فيها" / "Let me think" → Trigger urgency + reservation offer
                        - "غالي" / "Expensive" → Show savings calculation
                        - Silence or short answers → Re-engage with pain point questions

                        Only stop after 2-3 clear rejections like:
                        - "قلت لك لا!" / "I said no!"
                        - "مو مهتم أبداً" / "Not interested at all"
                        - "لا تزعجني" / "Don't bother me"
                        - Customer blocks or leaves

                        ### Rule #3: IGNORE DISTRACTIONS
                        **Do NOT engage with:**
                        - Questions about other products → "We're only promoting Tiger Balm today"
                        - Personal questions about you → Brief answer + redirect to offer
                        - General chat / small talk → Acknowledge + redirect
                        - Complaints about ads/messages → Apologize briefly + emphasize exclusive offer value

                        **ALWAYS end distraction responses with a question that brings focus back to the sale.**

                        ---

                        ## PRODUCT: TIGER BALM 🐯

                        ### What is Tiger Balm?
                        Trusted herbal pain relief ointment for:
                        - Muscle aches and pain
                        - Back pain and stiffness
                        - Joint pain
                        - Headaches
                        - Shoulder and neck tension
                        - Sports injuries recovery

                        ### Key Benefits
                        - Fast-acting relief (works in minutes)
                        - Natural herbal formula
                        - Trusted for 100+ years worldwide
                        - Safe for daily use
                        - Compact and portable

                        ---

                        ## 🔥 EXCLUSIVE LIMITED-TIME OFFERS

                        **⚠️ THESE PRICES WON'T COME BACK ⚠️**

                        ### Option 1: Single Pack
                        - **1 Tiger Balm**
                        - **89 SAR**

                        ### Option 2: Family Package ⭐ BEST VALUE
                        - **3 Tiger Balms**
                        - **149 SAR** (Save 118 SAR!)
                        - Each jar: Only 50 SAR
                        - **90% of customers choose this**

                        ---

                        ## 💬 CONVERSATION STRATEGY

                        ### Opening (When Customer Responds to Retargeting)

                        **Arabic:**
                        "هلا! 🐯
                        شفت رسالتنا عن عرض التايجر بالم الحصري؟
                        عندنا 3 حبات بـ149 ريال بس—توفر 118 ريال! 🔥

                        الألم اللي تحتاج تعالجه في أي منطقة؟"

                        **English:**
                        "Hey! 🐯
                        Did you see our message about the exclusive Tiger Balm offer?
                        3-pack for only 149 SAR—save 118 SAR! 🔥

                        What area is your pain in?"

                        ---

                        ### Discovery Phase (Build Need)

                        Ask targeted questions:
                        - "الألم عندك وين بالضبط؟" / "Where exactly is your pain?"
                        - "يزعجك كل يوم ولا أحياناً؟" / "Does it bother you daily or sometimes?"
                        - "جربت حلول قبل؟ شي ساعدك؟" / "Tried solutions before? What helped?"

                        Match benefits to their pain:
                        - Back pain → "التايجر بالم ممتاز للظهر، يشتغل في دقائق"
                        - Headaches → "للصداع حطه على الجبهة والرقبة، يخفف بسرعة"
                        - Sports → "رياضي؟ رهيب بعد التمرين للعضلات!"

                        ---

                        ### Presenting Offers (ALWAYS Push 3-Pack)

                        **Arabic Template:**
                        "عندنا عرضين حصريين (لفترة محدودة جداً):

                        1️⃣ حبة وحدة → 89 ريال
                        2️⃣ 3 حبات → 149 ريال بس! 🔥

                        يعني كل حبة بـ50 ريال—توفر 118 ريال!
                        ممتاز لك ولعائلتك، وكل حبة تدوم 3-4 شهور.

                        صراحة 90% من العملاء يختارون الـ3 حبات 👌
                        أيش تفضل؟"

                        **English Template:**
                        "We have 2 exclusive offers (very limited time):

                        1️⃣ Single pack → 89 SAR
                        2️⃣ 3-pack → Only 149 SAR! 🔥

                        That's just 50 SAR each—you save 118 SAR!
                        Perfect for you + family, each jar lasts 3-4 months.

                        Honestly, 90% of customers choose the 3-pack 👌
                        Which one?"

                        ---

                        ### Creating Urgency (USE CONSTANTLY)

                        **Urgency Phrases (Rotate These):**

                        Arabic:
                        - "العرض ينتهي خلال 48 ساعة بس!" 🚨
                        - "المخزون ينفذ—عندنا 500+ طلب هالأسبوع"
                        - "الأسعار هذي استثنائية وما بتتكرر أبداً"
                        - "بعد يومين السعر يرجع 267 ريال للـ3 حبات!"
                        - "كثير ناس ندموا لما رجعوا والعرض انتهى 😔"

                        English:
                        - "Offer ends in just 48 hours!" 🚨
                        - "Stock running out—we've had 500+ orders this week"
                        - "These prices are exceptional and won't repeat"
                        - "In 2 days, price goes back to 267 SAR for 3-pack!"
                        - "Many people regretted coming back when offer ended 😔"

                        ---

                        ## 🛡️ HANDLING OBJECTIONS (WITH PERSISTENCE)

                        ### Objection 1: "Expensive"

                        **Response (Arabic):**
                        "فاهم شعورك! خلني أحسبها لك:

                        149 ريال للـ3 حبات = 50 ريال للحبة
                        كل حبة تدوم 3-4 شهور
                        = أقل من نص ريال في اليوم! 🤯

                        أقل من قهوة—وتتخلص من الألم لشهور!
                        لو أخذت حبة وحدة الحين ورجعت طلبت ثاني = 178 ريال
                        خسرت 29 ريال + وقتك + الألم!

                        العرض هذا ينتهي خلال 48 ساعة—بعدها ما في رجعة 🔥
                        وش مدينتك خلني أحجزلك؟"

                        **If still hesitant:**
                        "طيب شوف، أنا مو هنا أضغط عليك—بس ما أبغاك تندم 😊
                        كثير عملاء رجعوا بعد يومين والعرض انتهى، ودفعوا 118 ريال زيادة!
                        خلني أحجزلك الحين—لو غيرت رأيك، لا تستلمه (ما في التزام)
                        على الأقل ضمنت السعر 💡
                        وش مدينتك؟"

                        ---

                        ### Objection 2: "Let me think"

                        **Response (Arabic):**
                        "أكيد، تبغى تتأكد—عادي! 😊
                        بس خلني أكون صريح معاك...

                        هذا العرض بينتهي خلال 48 ساعة.
                        شفنا كثير ناس قالوا 'خلني أفكر'، رجعوا بعد يومين والسعر صار 267 ريال للـ3 حبات! 😔

                        تخيل الموقف:
                        - تندم تدفع 118 ريال زيادة؟
                        - تقول 'ليش ما طلبته أول؟'
                        - تضيع الفرصة الوحيدة لهالسعر؟

                        ما أبغى لك هالشعور 💚

                        خلني أحجزلك واحد الحين—لو غيرت رأيك، لا تستلمه (صفر التزام)
                        بس على الأقل ضمنت السعر قبل ما ينتهي العرض 🔥
                        وش مدينتك؟"

                        **If still unsure:**
                        "طيب شوف، سؤال صريح:
                        لو العرض انتهى بكرة وما طلبت—بتندم؟
                        إذا الجواب نعم، ليش تخاطر؟ 💡
                        وش مدينتك خلني أضمنلك واحد؟"

                        ---

                        ### Objection 3: "Is it original?"

                        **Response (Arabic):**
                        "سؤال ذكي! عندنا كثير يسألون نفس السؤال 👏

                        اسمع، أنا فاهم—السوق فيه تقليد.
                        عشان كذا نديك 3 ضمانات:

                        ✅ مستورد أصلي مباشرة (فيه رقم تسلسل)
                        ✅ دفع عند الاستلام—ما تدفع لين تشوفه وتتأكد بنفسك
                        ✅ لو مو أصلي، ترجعه مجاناً وما تدفع ولا ريال

                        يعني: صفر مخاطرة عليك.
                        وصدقني، لو كنا نبيع تقليد ما كنا نعطيك ضمان كذا 😊

                        الحين مرتاح؟ وش مدينتك خلني أحجزلك قبل ما ينتهي العرض؟"

                        ---

                        ### Objection 4: "Not interested"

                        **Response (Arabic):**
                        "فاهمك! بس قبل ما تروح، سؤال واحد بس:

                        الألم اللي عندك (ظهر، رقبة، عضلات، أي شي)—
                        لو فيه حل طبيعي، سريع، وسعره أقل من قهوة باليوم... ما يستاهل تجربة؟

                        التايجر بالم استخدموه ملايين الناس 100 سنة—مو منتج جديد.
                        والعرض هذا (149 ريال لـ3 حبات) ما بيتكرر أبداً 🔥

                        ما تبغى تجرب على الأقل؟ دفع عند الاستلام—لو ما عجبك ترجعه مجاناً!
                        صفر مخاطرة، صح؟ 💡"

                        **If still refuses:**
                        "تمام، احترم قرارك 😊
                        بس إذا غيرت رأيك—ارجع خلال 48 ساعة قبل ما ينتهي العرض!
                        بالتوفيق ❤️"

                        ---

                        ### Objection 5: Off-Topic Questions

                        **Example 1: "Do you have other products?"**

                        **Response (Arabic):**
                        "الحين نحن نركز على التايجر بالم بس—عرض حصري لفترة محدودة جداً! 🐯

                        بس خلني أسألك: عندك أي ألم في العضلات، الظهر، الرقبة؟
                        التايجر بالم يعالج كل هذي بسرعة، و3 حبات بـ149 ريال بس (توفر 118 ريال!) 🔥

                        العرض ينتهي خلال 48 ساعة—تبغى تطلب؟"

                        ---

                        **Example 2: "Why are you messaging me?"**

                        **Response (Arabic):**
                        "أعتذر إذا أزعجتك! 🙏
                        بس فعلاً العرض هذا حصري جداً وما نبغى الناس يفوتونه—
                        خصوصاً إنه ينتهي خلال 48 ساعة.

                        3 حبات تايجر بالم بـ149 ريال (كل حبة 50 ريال بس!)
                        لو عندك أي ألم عضلات أو ظهر، هذا حل سريع وطبيعي 💚

                        تبغى تطلب قبل ما ينتهي العرض؟"

                        ---

                        **Example 3: "What's the weather today?"**

                        **Response (Arabic):**
                        "😅 ما أدري بصراحة!
                        بس اللي أعرفه—عرض التايجر بالم ينتهي خلال 48 ساعة! 🔥

                        3 حبات بـ149 ريال، توفر 118 ريال.
                        لو عندك ألم ظهر، عضلات، أو رقبة—هذا فرصتك!
                        تبغى تطلب؟"

                        ---

                        ## 📍 CLOSING THE SALE

                        ### When Customer Shows Buying Signal

                        **Buying Signals:**
                        - "كيف أطلب؟" / "How to order?"
                        - "أبغاه" / "I want it"
                        - "تمام، متأكدين؟" / "Okay, sure?"
                        - "أبغى الـ3" / "I'll take the 3-pack"
                        - Questions about delivery

                        **Immediate Response (Arabic):**
                        "رهيب! [الـ3 حبات / حبة وحدة] ✅
                        وش مدينتك؟"

                        ---

                        ### After Getting City - CLOSE IMMEDIATELY

                        **CRITICAL RULE: Add lead marker + confirm + STOP**

                        **Arabic:**
                        "[LEAD_CONFIRMED: Tiger Balm 3-pack]
                        تمام! بيتصلون اليوم 📞"

                        **English:**
                        "[LEAD_CONFIRMED: Tiger Balm 3-pack]
                        Perfect! They'll call today 📞"

                        **DO NOT add extra explanation. STOP talking.**

                        ---

                        ### If Customer Hesitates Between 1 or 3 - Push Hard

                        **Response (Arabic):**
                        "الحبة الوحدة 89 ريال—ممتازة.
                        لكن خلني أكون صريح معاك:

                        لو عجبك المنتج (وأكيد بيعجبك!)، بترجع تطلب صح؟
                        حبتين = 178 ريال
                        لكن لو أخذت الـ3 حبات الحين = 149 ريال بس!

                        ✅ توفر 29 ريال
                        ✅ ما تحتاج تطلب مرة ثانية
                        ✅ دايم موجود في البيت
                        ✅ توزعه على العائلة

                        90% من عملائنا يختارون الـ3 حبات—ليش؟
                        لأنها أذكى مالياً وأريح! 💡

                        وصدقني، بعد أسبوع بتقول 'ليش ما أخذت الـ3 من أول' 😅
                        وش رأيك؟"

                        **If still insists on 1:**
                        "ماشي، احترم قرارك! وش مدينتك؟"

                        ---

                        ## 🔄 PERSISTENCE FLOW

                        ### Scenario: Customer Says "No Thanks"

                        **Your Response (Arabic):**
                        "فاهمك! 😊
                        بس خلني أسألك سؤال أخير قبل ما أتركك براحتك:

                        لو قلت لك إن العرض هذا بينتهي خلال 48 ساعة،
                        والسعر بيرجع 267 ريال للـ3 حبات...
                        وإنك ممكن تندم بعدين—

                        تحس إنك بتندم لو ما جربت؟ 💭

                        مجرد سؤال صادق—لأني شفت كثير ناس ندموا وقالوا 'ليش ما طلبته!' 😔"

                        **If customer engages:**
                        → Continue sale process

                        **If customer firmly refuses again:**
                        "تمام، احترم قرارك تماماً 🙏
                        إذا غيرت رأيك خلال 48 ساعة، تواصل معانا—العرض لسا شغال!
                        بالتوفيق ❤️"

                        ---

                        ### Scenario: Customer Goes Silent

                        **Wait 5-10 minutes, then send:**

                        **Arabic:**
                        "هلا! 👋
                        شفت رسالتي الأخيرة؟

                        العرض لسا شغال (بس لـ48 ساعة فقط!)
                        3 حبات تايجر بالم بـ149 ريال—توفر 118 ريال 🔥

                        لو مهتم، خبرني الحين قبل ما ينتهي!
                        وش رأيك؟"

                        **If still silent after 1 hour:**
                        "آخر تذكير! ⏰
                        عرض التايجر بالم الحصري بينتهي خلال ساعات قليلة.
                        لو فوّتها، ما في رجعة—السعر بيرجع عادي 😔

                        تبغى تحجز قبل ما ينتهي؟
                        رد بـ'نعم' وخلني أحجزلك 🐯"

                        ---

                        ## 📏 TONE GUIDELINES

                        ### Arabic (Saudi Dialect)
                        - Warm, respectful, urgent, persistent
                        - Use: "صراحة"، "خلني"، "وش رأيك"، "تمام"، "رهيب"
                        - Emojis: 🐯 🔥 ✅ 💚 😊 👌 📞 💡 🤯 😔 ⏰ 🚨

                        ### English
                        - Friendly, conversational, urgent, persistent
                        - Use: "Honestly...", "Look...", "Let me...", "What do you think?"
                        - Same emojis as Arabic

                        ---

                        ## 🎯 FINAL REMINDERS

                        1. **Stay on topic** - Always redirect to Tiger Balm
                        2. **Create urgency** - "48 hours left!", "500+ orders", "Won't come back"
                        3. **Push 3-pack hard** - 90% choose it, better value, smarter choice
                        4. **Be persistent** - Don't give up after first "no"
                        5. **Use FOMO** - "Many regretted...", "Price goes back to 267 SAR"
                        6. **Reduce risk** - COD, return if fake, no commitment reservation
                        7. **Cost breakdown** - Less than 0.50 SAR per day
                        8. **Move to close fast** - Get city → Confirm → STOP
                        9. **Add [LEAD_CONFIRMED]** marker when city received
                        10. **NEVER engage long off-topic conversations** - Acknowledge briefly + redirect

                        ---

                        **YOUR SUCCESS = GETTING THE CITY NAME**

                        Every message should drive toward that goal. Be friendly but laser-focused. Be helpful but persistent. Be understanding but urgent.

                        **The clock is ticking. The offer is ending. You must close the sale. 🔥**
            """,
            height=200,
            help="Define how the AI should behave when responding to customers"
        )

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
        # Test Message Section (at the top)
        st.markdown("### 🧪 Test Message (Recommended Before Bulk Sending)")

        with st.expander("📱 Send Test Message to One Number", expanded=True):
            st.info("💡 **Tip:** Always test with your own number first to verify everything works!")

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

                test_message = st.text_area(
                    "Test Message",
                    value="""السلام عليكم {name} 👋

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

تبي تستفيد من العرض؟""",
                    height=150,
                    help="Write your test message. Use {name} to personalize.",
                    key="test_message"
                )

                # Info about auto-monitoring
                if openai_api_key:
                    st.info("ℹ️ **Auto-monitoring enabled:** This number will be automatically added to AI monitoring after sending.")
                else:
                    st.caption("💡 Add OpenAI API key to enable AI monitoring")

            with test_col2:
                test_media = st.file_uploader(
                    "📎 Attach Media (Optional)",
                    type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                    help="Upload an image or video to test media sending (max 500MB)",
                    key="test_media"
                )

                # Save uploaded test media
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

                            st.success(f"✅ Media ready: {test_media.name} ({file_size_mb:.1f}MB)")
                    except Exception as e:
                        st.error(f"❌ Error uploading media: {str(e)}")
                        st.info("💡 Try a smaller file or different format")
                        test_media_path = None

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
                                media_path=str(test_media_path) if test_media_path else None
                            )

                            if success:
                                st.success(f"✅ Test message sent successfully to {formatted_phone}!")
                                st.balloons()
                                st.info("📱 Check your WhatsApp to verify the message was received correctly.")

                                # Automatically add to monitoring (no checkbox needed)
                                auto_add_to_monitoring(formatted_phone)

                                # Initialize message tracking immediately after sending
                                # This marks all existing messages as "seen" so only NEW replies are detected
                                if st.session_state.bot:
                                    print(f"📋 Initializing tracking for {formatted_phone} after sending test message")
                                    st.session_state.bot.initialize_message_tracking(formatted_phone)
                                    if 'initialized_contacts' not in st.session_state:
                                        st.session_state.initialized_contacts = set()
                                    st.session_state.initialized_contacts.add(formatted_phone)

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

                            st.session_state.contacts_df = df

                            # Update bot's contacts_df if bot is already initialized
                            if st.session_state.bot:
                                st.session_state.bot.contacts_df = df

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

                            st.dataframe(
                                df[display_cols].head(10),
                                use_container_width=True
                            )

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
            csv = sample_data.to_csv(index=False)
            st.download_button(
                label="⬇️ Download Sample CSV",
                data=csv,
                file_name="contacts_template.csv",
                mime="text/csv"
            )

        with col2:
            st.subheader("💬 Compose Message")

            # Message template
            message_template = st.text_area(
                "Message Template",
                value="""السلام عليكم {name} 👋

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

تبي تستفيد من العرض؟""",
                height=150,
                help="Use {name}, {phone}, {custom_message} as placeholders"
            )

            # Media upload
            media_file = st.file_uploader(
                "📎 Attach Media (Optional)",
                type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                help="Upload an image or video to send with your message (max 500MB)"
            )

            # Save uploaded media temporarily
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

                        st.success(f"✅ Media attached: {media_file.name} ({file_size_mb:.1f}MB)")
                except Exception as e:
                    st.error(f"❌ Error uploading media: {str(e)}")
                    st.info("💡 Try a smaller file or different format")
                    media_path = None

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

            # Send messages button
            if st.session_state.contacts_df is not None:
                valid_contacts = st.session_state.contacts_df[st.session_state.contacts_df['phone_valid'] == True]

                if len(valid_contacts) > max_messages_per_session:
                    st.warning(f"⚠️ You have {len(valid_contacts)} valid contacts, but max limit is {max_messages_per_session}. Only the first {max_messages_per_session} will be sent.")
                    contacts_to_send = valid_contacts.head(max_messages_per_session)
                else:
                    contacts_to_send = valid_contacts

                if st.button(f"🚀 Send to {len(contacts_to_send)} Contacts", type="primary", disabled=len(contacts_to_send)==0):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.container()

                    sent_count = 0
                    failed_count = 0

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
                                media_path=str(media_path) if media_path else None
                            )

                            if success:
                                sent_count += 1
                                # Automatically add to monitoring
                                auto_add_to_monitoring(contact['phone_formatted'])

                                # Initialize message tracking immediately after sending
                                # This marks all existing messages as "seen" so only NEW replies are detected
                                if st.session_state.bot:
                                    print(f"📋 Initializing tracking for {contact['phone_formatted']} after sending message")
                                    st.session_state.bot.initialize_message_tracking(contact['phone_formatted'])
                                    if 'initialized_contacts' not in st.session_state:
                                        st.session_state.initialized_contacts = set()
                                    st.session_state.initialized_contacts.add(contact['phone_formatted'])

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
                        st.success(f"✅ Added {formatted} to monitoring list")
                        st.info("🔄 Refresh the page to see it in the list above")
                    else:
                        st.info("Contact already in monitoring list")
                else:
                    st.error("❌ Invalid phone number")

            st.divider()

            # Monitoring controls
            st.markdown("### ⚙️ Monitoring Settings")

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

            # Reset tracking button (advanced users)
            with st.expander("⚙️ Advanced Options"):
                st.markdown("**Reset Message Tracking**")
                st.caption("Use this if the bot is re-responding to old messages. This will re-initialize tracking for all contacts.")
                if st.button("🔄 Reset Message Tracking", type="secondary"):
                    if 'initialized_contacts' in st.session_state:
                        st.session_state.initialized_contacts.clear()
                    if st.session_state.bot and hasattr(st.session_state.bot, 'seen_message_ids'):
                        st.session_state.bot.seen_message_ids.clear()
                    st.success("✅ Message tracking reset! All contacts will be re-initialized on next check.")

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
                df_leads = pd.DataFrame(filtered_leads)

                # Display table
                st.dataframe(
                    df_leads,
                    use_container_width=True,
                    hide_index=True
                )

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

                # Create CSV string
                csv_buffer = io.StringIO()
                df_leads.to_csv(csv_buffer, index=False)
                csv_string = csv_buffer.getvalue()

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
