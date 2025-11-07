# Deployment Guide for Streamlit App

This guide covers how to securely deploy your WhatsApp bulk messaging bot with proper API key handling.

## 🔐 Security Best Practices

### **CRITICAL: Never Expose API Keys in Code or UI**

When deploying the Streamlit app:
1. ✅ **Always use .env file** for API keys
2. ❌ **Never** enter API keys in the web UI when deployed
3. ✅ **Keep .env file out of version control** (already in .gitignore)
4. ✅ **Use environment variables** on your deployment platform

## 🚀 Deployment Options

### Option 1: Local Deployment (Private Network)

Best for: Internal use, private network, testing

```bash
# 1. Set up environment
cp .env.example .env
nano .env  # Add your real API key

# 2. Launch app
streamlit run streamlit_app.py

# 3. Access on local network
# App runs at: http://localhost:8501
# Or from other devices: http://YOUR_LOCAL_IP:8501
```

**Security:**
- ✅ API key stored in .env file
- ✅ Not exposed in UI
- ✅ Only accessible on your network

### Option 2: Streamlit Cloud (Public Deployment)

Best for: Sharing with team, remote access

**⚠️ NOT RECOMMENDED for public access due to WhatsApp automation risks**

If you must deploy to Streamlit Cloud:

```bash
# 1. Push code to GitHub (API keys already gitignored)
git push origin main

# 2. Go to: https://share.streamlit.io

# 3. Connect your GitHub repository

# 4. In Streamlit Cloud dashboard:
#    - Go to App Settings → Secrets
#    - Add your secrets:
```

```toml
# .streamlit/secrets.toml format
OPENAI_API_KEY = "sk-your-actual-api-key-here"
```

**Security Notes:**
- ✅ Secrets are encrypted
- ✅ Not visible in UI
- ✅ Not in version control
- ⚠️ Requires authentication to access app
- ⚠️ Use with caution - WhatsApp may ban automated accounts

### Option 3: Docker Container (Recommended for Production)

Best for: Production deployment, VPS/cloud servers, better isolation

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install Chrome and dependencies for Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Run app
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  whatsapp-bot:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    volumes:
      - ./whatsapp_profile:/app/whatsapp_profile
      - ./temp_media:/app/temp_media
    restart: unless-stopped
```

**Deploy:**

```bash
# 1. Make sure .env file has your API key
cp .env.example .env
nano .env  # Add real API key

# 2. Build and run
docker-compose up -d

# 3. Access at: http://localhost:8501
```

**Security:**
- ✅ API key in .env file (not in image)
- ✅ Isolated container
- ✅ Easy to redeploy
- ✅ Volume persistence for WhatsApp session

### Option 4: VPS/Cloud Server (DigitalOcean, AWS, etc.)

Best for: Full control, production use

**Setup on Ubuntu Server:**

```bash
# 1. SSH into your server
ssh user@your-server-ip

# 2. Install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv git

# 3. Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# 4. Clone repository
git clone https://github.com/your-username/wtsp_retarget.git
cd wtsp_retarget

# 5. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 6. Install requirements
pip install -r requirements.txt

# 7. Set up .env file
cp .env.example .env
nano .env  # Add your API key

# 8. Run with screen (keeps running after logout)
screen -S whatsapp-bot
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

# Detach: Ctrl+A, then D
# Reattach: screen -r whatsapp-bot
```

**Security with Nginx Reverse Proxy + HTTPS:**

```nginx
# /etc/nginx/sites-available/whatsapp-bot
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site and get SSL certificate
sudo ln -s /etc/nginx/sites-available/whatsapp-bot /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

**Security:**
- ✅ HTTPS encryption
- ✅ Password protection (add basic auth to Nginx)
- ✅ API key in .env file
- ✅ Firewall rules
- ✅ Automatic SSL renewal

## 🛡️ Additional Security Measures

### 1. Password Protection

Add authentication to your Streamlit app:

```python
# Add to streamlit_app.py at the top
import streamlit as st

def check_password():
    """Returns True if password is correct."""
    def password_entered():
        if st.session_state["password"] == os.getenv("APP_PASSWORD", "default"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("Password incorrect")
        return False
    else:
        return True

if not check_password():
    st.stop()

# Rest of your app...
```

Add to .env:
```
APP_PASSWORD=your-secure-password-here
```

### 2. IP Whitelisting

Using Nginx:

```nginx
location / {
    allow 1.2.3.4;      # Your IP
    allow 5.6.7.8/24;   # Your office network
    deny all;

    proxy_pass http://localhost:8501;
    # ... rest of config
}
```

### 3. Environment Variable Validation

The app already checks for .env file and shows warnings if API key is not set.

### 4. Monitoring & Logging

```bash
# Check app logs
screen -r whatsapp-bot  # See live output

# Docker logs
docker-compose logs -f

# System logs
journalctl -u streamlit-bot -f
```

## 📋 Pre-Deployment Checklist

Before deploying to production:

- [ ] ✅ API key is in .env file (not in code)
- [ ] ✅ .env file is in .gitignore
- [ ] ✅ Test locally first
- [ ] ✅ Set up password protection (if needed)
- [ ] ✅ Configure HTTPS (if public)
- [ ] ✅ Set up IP whitelisting (if needed)
- [ ] ✅ Test all features work in deployment environment
- [ ] ✅ Set up monitoring/logging
- [ ] ✅ Document access credentials securely
- [ ] ✅ Backup WhatsApp session files regularly
- [ ] ✅ Review WhatsApp Terms of Service

## ⚠️ Important Warnings

1. **WhatsApp Account Risks:**
   - Automation may violate WhatsApp ToS
   - Use a business/test number, not personal
   - Respect rate limits (40-50 messages/day)
   - Always get consent before messaging

2. **API Key Security:**
   - Never commit API keys to Git
   - Never share .env file
   - Rotate keys if exposed
   - Monitor OpenAI usage dashboard

3. **Server Security:**
   - Keep system updated
   - Use firewall
   - Regular backups
   - Monitor for unauthorized access

## 🔄 Updating Deployed App

```bash
# Pull latest changes
git pull origin main

# Restart app
# Screen:
screen -r whatsapp-bot
# Ctrl+C to stop, then restart

# Docker:
docker-compose down && docker-compose up -d

# Check it's running
curl http://localhost:8501
```

## 🆘 Troubleshooting

### API Key Not Loading

```bash
# Check .env file exists
ls -la .env

# Check .env content (don't share output!)
cat .env

# Test loading in Python
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('OPENAI_API_KEY')[:10])"
```

### Port Already in Use

```bash
# Find process using port 8501
sudo lsof -i :8501

# Kill it
sudo kill -9 <PID>
```

### Chrome/Selenium Issues in Docker

Make sure Chrome is installed in container and use headless mode.

## 📧 Support

For deployment issues:
1. Check this guide
2. Review logs
3. Test locally first
4. Check firewall/network settings

---

**Remember:** Always prioritize security, especially with API keys and WhatsApp automation! 🔐
