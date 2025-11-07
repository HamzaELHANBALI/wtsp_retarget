# Project Structure & Dependencies

This document provides a comprehensive overview of the project's file structure, dependencies, and what files are necessary for different use cases.

## 📁 File Overview

```
wtsp_retarget/
├── 🎯 ENTRY POINTS
│   ├── test_bot.py              # CLI entry point for command-line usage
│   └── streamlit_app.py         # Web UI entry point for browser-based usage
│
├── 🔧 CORE MODULES
│   ├── whatsapp_bot.py          # Main bot logic (used by both entry points)
│   └── clean_order_csv.py       # CSV cleaning utilities
│
├── ⚙️ CONFIGURATION
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Environment variable template
│   ├── .gitignore              # Git ignore rules
│   └── .streamlit/
│       └── config.toml          # Streamlit-specific settings
│
├── 📚 DOCUMENTATION
│   ├── README.md                # Main documentation
│   ├── CSV_CLEANING_GUIDE.md    # CSV cleaning guide
│   ├── DEPLOYMENT.md            # Deployment instructions
│   └── PROJECT_STRUCTURE.md     # This file
│
├── 📋 TEMPLATES
│   └── contacts_template.csv    # Sample CSV format
│
└── 🧪 TESTING/DEBUG
    ├── test_phone_cleaning.py   # Unit tests for cleaning functions
    └── debug_whatsapp.py        # WhatsApp Web debugging tool
```

## 🔀 Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                          │
└────────────┬──────────────────────────────────┬─────────────────┘
             │                                  │
             ▼                                  ▼
    ┌────────────────┐                ┌─────────────────┐
    │  test_bot.py   │                │ streamlit_app.py│
    │   (CLI Mode)   │                │   (Web UI)      │
    └────────┬───────┘                └────────┬────────┘
             │                                  │
             │         ┌────────────────────────┤
             │         │                        │
             ▼         ▼                        ▼
         ┌──────────────────────┐      ┌──────────────────┐
         │  whatsapp_bot.py     │      │ clean_order_csv. │
         │  (Core Bot Logic)    │      │ py (CSV Utils)   │
         └──────────┬───────────┘      └──────────────────┘
                    │
                    │ uses
                    ▼
    ┌───────────────────────────────────────────┐
    │         EXTERNAL DEPENDENCIES             │
    ├───────────────────────────────────────────┤
    │ • selenium (WhatsApp Web automation)      │
    │ • openai (AI responses)                   │
    │ • pandas (Data processing)                │
    │ • streamlit (Web UI framework)            │
    │ • python-dotenv (Environment variables)   │
    └───────────────────────────────────────────┘
                    │
                    │ requires
                    ▼
            ┌───────────────┐
            │  .env file    │
            │  (API keys)   │
            └───────────────┘
```

## 📊 File Dependencies by Use Case

### 🖥️ **Running test_bot (CLI Mode)**

**Minimum Required Files:**
```
✅ test_bot.py              # Entry point
✅ whatsapp_bot.py          # Core logic
✅ requirements.txt         # Dependencies
✅ .env                     # API keys (created from .env.example)
```

**Optional but Recommended:**
```
📖 README.md                # Documentation
📖 .env.example            # Template for .env
```

**Auto-Generated (don't need to track):**
```
📁 whatsapp_profile/       # Browser session data
📁 __pycache__/            # Python cache
```

---

### 🌐 **Running streamlit_app (Web UI Mode)**

**Minimum Required Files:**
```
✅ streamlit_app.py         # Entry point
✅ whatsapp_bot.py          # Core logic
✅ clean_order_csv.py       # CSV utilities
✅ requirements.txt         # Dependencies
✅ .env                     # API keys
✅ .streamlit/config.toml   # Streamlit settings
```

**Optional but Recommended:**
```
📋 contacts_template.csv    # Sample CSV for users
📖 README.md                # Documentation
📖 CSV_CLEANING_GUIDE.md   # CSV help
📖 DEPLOYMENT.md           # Deployment guide
```

**Auto-Generated:**
```
📁 whatsapp_profile/       # Browser session data
📁 temp_media/             # Uploaded media files
📁 __pycache__/            # Python cache
```

---

### 🧪 **Development & Testing**

**For Testing CSV Functions:**
```
✅ test_phone_cleaning.py   # Unit tests
✅ clean_order_csv.py       # Functions to test
```

**For Debugging WhatsApp Selectors:**
```
✅ debug_whatsapp.py        # Debug tool
✅ whatsapp_bot.py          # Module being debugged
```

---

## 🔍 Detailed File Descriptions

### Entry Points

#### `test_bot.py` (CLI Mode)
- **Purpose:** Command-line interface for quick bot testing
- **Size:** ~100 lines
- **Dependencies:** whatsapp_bot.py, .env
- **Use Case:** Quick tests, scripting, cron jobs
- **Example:**
  ```python
  from whatsapp_bot import WhatsAppBot
  bot = WhatsAppBot()
  bot.send_message("+966501234567", "Hello!")
  ```

#### `streamlit_app.py` (Web UI Mode)
- **Purpose:** Full-featured web interface
- **Size:** 1,089 lines
- **Dependencies:** whatsapp_bot.py, clean_order_csv.py, .env, .streamlit/config.toml
- **Features:**
  - 📤 Bulk messaging from CSV
  - 🤖 AI-powered monitoring & responses
  - 📊 Analytics dashboard
  - 📁 CSV file upload
  - 🖼️ Media attachment support
- **Use Case:** Production use, user-friendly interface

---

### Core Modules

#### `whatsapp_bot.py` (Shared Core)
- **Purpose:** Main WhatsApp automation logic
- **Size:** 1,185 lines
- **Key Classes:**
  - `WhatsAppBot`: Main bot class
- **Key Features:**
  - Selenium WebDriver management
  - WhatsApp Web login & session handling
  - Message sending (text + media)
  - Message monitoring & reading
  - AI response generation (OpenAI GPT-4)
  - Conversation tracking
  - Statistics & analytics
- **Used by:** Both test_bot.py and streamlit_app.py

#### `clean_order_csv.py`
- **Purpose:** E-commerce CSV data cleaning
- **Size:** 298 lines
- **Key Functions:**
  - `convert_arabic_numerals()`: ٠-٩ → 0-9
  - `clean_phone_number()`: Normalize to +966 format
  - `clean_name()`: Remove special chars
  - `clean_csv_file()`: Process entire CSV
- **Used by:** streamlit_app.py (CSV upload processing)
- **Can run standalone:** Yes (command-line usage)

---

### Configuration Files

#### `requirements.txt`
- **Purpose:** Python package dependencies
- **Key Packages:**
  - selenium==4.15.2 (Web automation)
  - openai==1.3.5 (AI responses)
  - streamlit==1.28.1 (Web UI)
  - pandas==2.1.3 (Data processing)
  - python-dotenv==1.0.0 (Environment variables)

#### `.env.example`
- **Purpose:** Template for environment variables
- **Required Variables:**
  ```bash
  OPENAI_API_KEY=sk-...
  ```
- **Usage:** Copy to `.env` and fill in actual values

#### `.streamlit/config.toml`
- **Purpose:** Streamlit-specific settings
- **Key Settings:**
  - Max upload size: 500MB
  - Theme: Light mode
  - CORS: Disabled for local use

#### `.gitignore`
- **Purpose:** Exclude sensitive/generated files from Git
- **Excludes:**
  - .env (API keys)
  - whatsapp_profile/ (browser data)
  - temp_media/ (uploads)
  - __pycache__/ (Python cache)

---

### Documentation

#### `README.md`
- **Size:** 561 lines
- **Sections:**
  - Features overview
  - Quick start (CLI & Web UI)
  - Usage examples
  - Troubleshooting
  - Security best practices

#### `CSV_CLEANING_GUIDE.md`
- **Size:** 260 lines
- **Purpose:** Guide for cleaning e-commerce CSV files
- **Covers:**
  - Expected CSV format
  - Phone number normalization
  - Arabic numeral conversion
  - Testing examples

#### `DEPLOYMENT.md`
- **Size:** 386 lines
- **Purpose:** Production deployment instructions
- **Deployment Options:**
  - Local development
  - Docker containers
  - VPS deployment
  - Streamlit Cloud
  - HTTPS/Nginx setup

---

### Templates

#### `contacts_template.csv`
- **Purpose:** Sample CSV format for users
- **Columns:** name, phone, message
- **Includes:** 5 example contacts
- **Usage:** Download from Streamlit UI as reference

---

### Testing & Debug Tools

#### `test_phone_cleaning.py`
- **Purpose:** Unit tests for cleaning functions
- **Size:** 114 lines
- **Tests:**
  - Arabic numeral conversion
  - Phone number normalization (+966)
  - Name cleaning
- **Usage:** `python test_phone_cleaning.py`

#### `debug_whatsapp.py`
- **Purpose:** Interactive WhatsApp Web element inspector
- **Size:** 129 lines
- **Use Case:** When WhatsApp UI changes and selectors break
- **Features:**
  - Live element inspection
  - Selector testing
  - Screenshot capture

---

## 🚀 Quick Start Commands

### Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create environment file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run in your preferred mode:
```

### CLI Mode
```bash
python test_bot.py
```

### Web UI Mode
```bash
streamlit run streamlit_app.py
```

### Testing
```bash
python test_phone_cleaning.py
```

### Debug WhatsApp
```bash
python debug_whatsapp.py
```

---

## 🗑️ Files You Can Safely Delete

**NONE!** All files in the repository serve a purpose:

- **Core files:** Required for functionality
- **Documentation:** Essential for users
- **Templates:** Useful references
- **Tests/Debug:** Helpful for development

---

## 📦 Auto-Generated Directories (Not in Git)

These are created automatically and excluded from version control:

| Directory | Purpose | Created By |
|-----------|---------|------------|
| `whatsapp_profile/` | Browser session data | whatsapp_bot.py |
| `temp_media/` | Uploaded media files | streamlit_app.py |
| `__pycache__/` | Python bytecode cache | Python interpreter |
| `.env` | API keys & secrets | User (from .env.example) |

---

## 🔄 Update Strategy

### When WhatsApp Web Changes
1. Run `debug_whatsapp.py` to find new selectors
2. Update selectors in `whatsapp_bot.py`
3. Test with `test_bot.py`
4. Deploy updated `streamlit_app.py`

### When Adding Features
1. Add logic to `whatsapp_bot.py` (core functionality)
2. Update `test_bot.py` for CLI usage
3. Update `streamlit_app.py` for Web UI
4. Update `README.md` with new features
5. Add tests to `test_phone_cleaning.py` if applicable

### When Deploying
1. Review `DEPLOYMENT.md`
2. Ensure `.env` is configured
3. Update `requirements.txt` if new dependencies added
4. Test locally with `streamlit run streamlit_app.py`
5. Deploy to your chosen platform

---

## 🎯 Maintenance Checklist

### Weekly
- [ ] Check for WhatsApp Web UI changes
- [ ] Review logs for errors

### Monthly
- [ ] Update dependencies in `requirements.txt`
- [ ] Run `test_phone_cleaning.py`
- [ ] Review and update documentation

### As Needed
- [ ] Update OpenAI API key in `.env`
- [ ] Clear old browser profiles in `whatsapp_profile/`
- [ ] Clean up old media in `temp_media/`

---

## 📞 Support

If you need help:
1. Check `README.md` for common issues
2. Review `CSV_CLEANING_GUIDE.md` for CSV problems
3. Check `DEPLOYMENT.md` for deployment issues
4. Use `debug_whatsapp.py` for WhatsApp selector issues

---

**Last Updated:** 2025-11-07
**Project Version:** 2.0
**Maintained By:** HamzaELHANBALI
