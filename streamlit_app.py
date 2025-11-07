import streamlit as st
import pandas as pd
import time
import os
import re
from pathlib import Path
from datetime import datetime
import threading
from whatsapp_bot import WhatsAppBot

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

# Helper functions
def validate_phone_number(phone):
    """Validate phone number format"""
    if pd.isna(phone):
        return False
    phone_str = str(phone).strip()
    # Remove common separators
    phone_str = re.sub(r'[\s\-\(\)]', '', phone_str)
    # Check if it's a valid format (with or without + and country code)
    if re.match(r'^\+?\d{10,15}$', phone_str):
        return True
    return False

def format_phone_number(phone, country_code="+966"):
    """Format phone number with country code"""
    phone_str = str(phone).strip()
    # Remove common separators
    phone_str = re.sub(r'[\s\-\(\)]', '', phone_str)

    # If it already has +, return as is
    if phone_str.startswith('+'):
        return phone_str

    # If it starts with country code without +, add +
    if phone_str.startswith(country_code.replace('+', '')):
        return '+' + phone_str

    # If it starts with 0, remove it and add country code
    if phone_str.startswith('0'):
        phone_str = phone_str[1:]

    # Add country code
    return country_code + phone_str

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

    # API Key
    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        help="Enter your OpenAI API key for AI responses",
        value=os.getenv("OPENAI_API_KEY", "")
    )

    # Country Code
    country_code = st.selectbox(
        "Country Code",
        options=["+966", "+971", "+20", "+1", "+44", "+33", "+49"],
        index=0,
        help="Select your country code for phone number formatting"
    )

    # System Prompt
    with st.expander("🤖 AI System Prompt"):
        system_prompt = st.text_area(
            "Customize AI Behavior",
            value="""You are a helpful customer service assistant for a business.
Respond professionally and courteously to customer inquiries.
Keep responses concise and helpful. Always be polite and friendly.""",
            height=150,
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

    if not st.session_state.logged_in:
        if st.button("🚀 Initialize Bot & Login", type="primary"):
            with st.spinner("Initializing bot... Please wait for QR code"):
                try:
                    # Initialize bot
                    st.session_state.bot = WhatsAppBot(
                        openai_api_key=openai_api_key if openai_api_key else None,
                        system_prompt=system_prompt,
                        headless=False
                    )
                    st.session_state.logged_in = True
                    st.success("✅ Bot initialized! You should see WhatsApp Web in a browser window.")
                    st.info("📱 Scan the QR code with your phone to login")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to initialize bot: {str(e)}")
    else:
        st.success("✅ Bot is active")
        if st.button("🔌 Disconnect", type="secondary"):
            if st.session_state.bot:
                st.session_state.bot.close()
            st.session_state.bot = None
            st.session_state.logged_in = False
            st.session_state.monitoring = False
            st.rerun()

    st.divider()

    # Statistics
    st.header("📊 Session Stats")
    if st.session_state.bot:
        stats = st.session_state.bot.get_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages Sent", stats.get('messages_sent', 0))
            st.metric("AI Responses", stats.get('ai_responses', 0))
        with col2:
            st.metric("Success Rate", f"{stats.get('success_rate', 0):.0%}")
            st.metric("Conversations", len(stats.get('conversation_history', {})))

# Main content area - Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📤 Bulk Messaging", "🤖 AI Auto-Responder", "📊 Analytics", "❓ Help"])

# Tab 1: Bulk Messaging
with tab1:
    if not st.session_state.logged_in:
        st.warning("⚠️ Please initialize the bot and login to WhatsApp first (see sidebar)")
    else:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("📋 Upload Contacts")

            # CSV Upload
            uploaded_file = st.file_uploader(
                "Upload CSV file",
                type=['csv'],
                help="Upload a CSV file with columns: phone, name, custom_message (optional)"
            )

            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file)

                    # Validate required columns
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

                        # Validate and format phone numbers
                        df['phone_valid'] = df['phone'].apply(validate_phone_number)
                        df['phone_formatted'] = df.apply(
                            lambda row: format_phone_number(row['phone'], country_code) if row['phone_valid'] else row['phone'],
                            axis=1
                        )

                        st.session_state.contacts_df = df

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
                        st.dataframe(
                            df[['phone', 'phone_formatted', 'name', 'phone_valid']].head(10),
                            use_container_width=True
                        )

                except Exception as e:
                    st.error(f"❌ Error reading CSV: {str(e)}")

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
                value="Hello {name}! 👋\n\nWe have an exciting update for you!\n\n{custom_message}",
                height=150,
                help="Use {name}, {phone}, {custom_message} as placeholders"
            )

            # Media upload
            media_file = st.file_uploader(
                "📎 Attach Media (Optional)",
                type=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'],
                help="Upload an image or video to send with your message"
            )

            # Save uploaded media temporarily
            media_path = None
            if media_file is not None:
                # Save to temp location
                temp_dir = Path("temp_media")
                temp_dir.mkdir(exist_ok=True)
                media_path = temp_dir / media_file.name
                with open(media_path, "wb") as f:
                    f.write(media_file.getbuffer())
                st.success(f"✅ Media attached: {media_file.name}")

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
                monitored_contacts = st.multiselect(
                    "Select contacts to monitor",
                    options=st.session_state.contacts_df['phone_formatted'].tolist(),
                    help="Select which contacts the bot should monitor and respond to"
                )
            else:
                st.info("Upload contacts in the Bulk Messaging tab first")
                monitored_contacts = []

            # Manual contact addition
            manual_phone = st.text_input(
                "Or add phone manually",
                placeholder="+966501234567",
                help="Enter a phone number to monitor"
            )

            if manual_phone and st.button("➕ Add Contact"):
                if validate_phone_number(manual_phone):
                    formatted = format_phone_number(manual_phone, country_code)
                    if formatted not in monitored_contacts:
                        monitored_contacts.append(formatted)
                        st.success(f"✅ Added {formatted}")
                    else:
                        st.info("Contact already in list")
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

            # Start/Stop monitoring
            if not st.session_state.monitoring:
                if st.button("▶️ Start Monitoring", type="primary", disabled=len(monitored_contacts)==0):
                    if not openai_api_key:
                        st.error("❌ Please enter OpenAI API key in sidebar")
                    else:
                        st.session_state.monitoring = True
                        st.session_state.bot.monitored_contacts = monitored_contacts
                        st.success("✅ Monitoring started!")
                        st.info(f"Monitoring {len(monitored_contacts)} contacts. The bot will respond automatically to new messages.")
                        st.rerun()
            else:
                if st.button("⏸️ Stop Monitoring", type="secondary"):
                    st.session_state.monitoring = False
                    st.info("Monitoring stopped")
                    st.rerun()

        with col2:
            st.markdown("### 💬 Live Activity")

            if st.session_state.monitoring:
                st.info(f"🟢 Monitoring {len(monitored_contacts)} contacts (checking every {check_interval}s)")

                # Placeholder for live messages
                messages_container = st.container()

                # Run monitoring loop
                with messages_container:
                    st.markdown("#### Recent Interactions")

                    # Display conversation history
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
                            st.info("No conversations yet. Waiting for messages...")

                    # Auto-refresh every check_interval seconds
                    if st.button("🔄 Refresh"):
                        st.rerun()

                    st.caption("💡 Tip: The bot is running in the background. Refresh to see new messages.")
            else:
                st.info("👆 Select contacts and click 'Start Monitoring' to begin")

# Tab 3: Analytics
with tab3:
    st.subheader("📊 Analytics Dashboard")

    if st.session_state.bot:
        stats = st.session_state.bot.get_stats()

        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📤 Messages Sent", stats.get('messages_sent', 0))
        with col2:
            st.metric("🤖 AI Responses", stats.get('ai_responses', 0))
        with col3:
            success_rate = stats.get('success_rate', 0)
            st.metric("✅ Success Rate", f"{success_rate:.0%}")
        with col4:
            conversations = len(stats.get('conversation_history', {}))
            st.metric("💬 Active Conversations", conversations)

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
with tab4:
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
