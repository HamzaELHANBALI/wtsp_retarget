"""
Test script for WhatsApp Bot
Demonstrates sending messages and AI auto-responses
"""

from whatsapp_bot import WhatsAppBot
import os
import json
from pathlib import Path

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
        return None
    except Exception as e:
        print(f"⚠️ Error loading initial_message.json: {e}")
        return None

# Configuration
CONTACTS = [
    "+33631055810"
    # Add more contacts as needed
]

# Load initial message from JSON file
_default_message = load_initial_message()
if _default_message is None:
    # Fallback to hardcoded message if JSON file doesn't exist (matches initial_message.json format)
    MESSAGE = "السلام عليكم Customer 👋 كيف حالك؟"
else:
    # Use message from JSON file - replace {name} placeholder with "Customer" for testing
    MESSAGE = _default_message.replace("{name}", "Customer")

# Optional: Media file paths
# Set to None for text-only, or provide path to image/video
# Main media: Sent after customer responds
MEDIA_FILE = "/Users/hamzaelhanbali/Desktop/personal/tiger/hamza_tiger_27_octobre_1.mp4"  # Update this path
# Second media (free product): Sent immediately after main media
MEDIA_FILE_2 = None  # Optional: Path to free product media (e.g., electric ashtray)

# Load AI System Prompt from JSON file (defaults to lighter watch bundle)
# Change prompt_file_name to use a different prompt file
prompt_file_name = None  # None = use default (lighter watch bundle), or specify: "noura_electric_ashtray_prompt.json"
_default_prompt = load_noura_prompt(prompt_file_name)
if _default_prompt is None:
    # Fallback to hardcoded prompt if JSON file doesn't exist
    SYSTEM_PROMPT = """
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
else:
    # Use prompt from JSON file
    SYSTEM_PROMPT = _default_prompt


def main():
    """Main test function"""

    print("="*60)
    print("WhatsApp Bulk Messaging Bot - Test")
    print("="*60)
    print(f"\n📋 Configuration:")
    print(f"   Contacts: {len(CONTACTS)}")
    print(f"   Main Media: {'Yes' if MEDIA_FILE else 'No'}")
    print(f"   Second Media (Free Product): {'Yes' if MEDIA_FILE_2 else 'No'}")
    print(f"   AI: Enabled (if API key configured)")
    # List available prompts
    available_prompts = list_available_prompt_files()
    prompt_source = prompt_file_name if prompt_file_name else ("noura_lighter_watch_bundle_prompt.json" if "noura_lighter_watch_bundle_prompt.json" in available_prompts else ("noura_electric_ashtray_prompt.json" if "noura_electric_ashtray_prompt.json" in available_prompts else ("noura_prompt.json" if "noura_prompt.json" in available_prompts else "default")))
    
    print(f"   Initial Message: Loaded from initial_message.json" if _default_message else "   Initial Message: Using fallback")
    print(f"   System Prompt: Loaded from {prompt_source}" if _default_prompt else "   System Prompt: Using fallback")
    print(f"   Available prompt files: {', '.join(available_prompts) if available_prompts else 'None'}")
    print(f"   Follow-up Message: Loaded automatically from followup_message.json (if enabled)")
    print("\n" + "="*60 + "\n")

    # Initialize bot
    # Note: Follow-up messages are automatically loaded from followup_message.json
    # The bot will use the JSON file if it exists, otherwise it will use the default
    try:
        # Initialize bot in test mode (skip bot_state.json - reserved for real customers)
        bot = WhatsAppBot(system_prompt=SYSTEM_PROMPT, test_mode=True)
        # Configure follow-up settings (optional - defaults are in WhatsAppBot)
        # bot.followup_enabled = True  # Enable follow-ups (default: True)
        # bot.followup_delay_minutes = 60  # Delay before follow-up in minutes (default: 60)
        print("✅ Bot initialized successfully (test mode - bot_state.json skipped)")
        print(f"   Follow-up enabled: {bot.followup_enabled}")
        print(f"   Follow-up delay: {bot.followup_delay_minutes} minutes")
    except Exception as e:
        print(f"❌ Failed to initialize bot: {e}")
        return

    try:
        # Step 1: Send messages to all contacts
        print("📤 STEP 1: Sending messages to contacts\n")

        for i, contact in enumerate(CONTACTS, 1):
            print(f"[{i}/{len(CONTACTS)}] Sending to {contact}...")

            success = bot.send_message(
                phone=contact,
                message=MESSAGE,
                media_path=MEDIA_FILE,
                media_path_2=MEDIA_FILE_2
            )

            if success:
                print(f"   ✅ Sent successfully")
            else:
                print(f"   ❌ Failed")

            # Wait between messages (except for last one)
            if i < len(CONTACTS):
                import time
                wait_time = 5
                print(f"   ⏳ Waiting {wait_time}s before next send...\n")
                time.sleep(wait_time)

        print("\n" + "="*60)
        print("✅ All messages sent!")
        print("="*60)

        # Step 2: Start monitoring for responses
        print("\n📤 STEP 2: Starting AI monitoring\n")
        print("The bot will now:")
        print("   - Check for incoming messages every 10 seconds")
        print("   - Automatically respond using AI")
        print("   - Maintain conversation context per contact")
        if bot.followup_enabled:
            print(f"   - Send follow-up messages after {bot.followup_delay_minutes} minutes if no response")
        print("\n   Press Ctrl+C to stop monitoring\n")
        print("="*60 + "\n")

        # Monitor indefinitely (or set duration in seconds)
        bot.monitor_and_respond(
            check_interval=10,    # Check every 10 seconds
            duration=None         # None = run forever, or set seconds
        )

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        bot.close()
        print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
