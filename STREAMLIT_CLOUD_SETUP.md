# Streamlit Cloud Deployment Setup

## Quick Setup Guide

The app is deployed at: **[https://zillow-agent-demo.streamlit.app/](https://zillow-agent-demo.streamlit.app/)**

## Setting Up Secrets in Streamlit Cloud

Streamlit Cloud **does not** read `.env` files. You must configure secrets in the Streamlit Cloud dashboard.

### Steps:

1. **Go to Streamlit Cloud Dashboard**
   - Visit [https://share.streamlit.io](https://share.streamlit.io)
   - Sign in and navigate to your app

2. **Open Settings**
   - Click on the **Settings** (⚙️) icon in the top right
   - Select **Secrets** from the menu

3. **Add Your Secrets**
   - Click **"Edit secrets"** or the **"+"** button
   - Paste the following template and fill in your actual API keys:

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
ANTHROPIC_MODEL = "claude-3-haiku-20240307"
RAPIDAPI_KEY = "92fbc13ef2msh..."
ZILLOW_API_BASE_URL = "https://real-time-zillow-data.p.rapidapi.com"
ZILLOW_API_HOST = "real-time-zillow-data.p.rapidapi.com"
ZILLOW_MARKET_API_BASE_URL = "https://zillow-working-api.p.rapidapi.com"
ZILLOW_MARKET_API_HOST = "zillow-working-api.p.rapidapi.com"
```

4. **Save and Restart**
   - Click **"Save"**
   - The app will automatically restart
   - Wait for the deployment to complete

5. **Verify**
   - Visit your app URL
   - Try a search query (e.g., "Find houses in Las Vegas")
   - The app should now work with API keys from secrets

## Troubleshooting

### Error: "ANTHROPIC_API_KEY environment variable not set"

**Solution**: Make sure you've added the secrets in Streamlit Cloud:
1. Go to Settings → Secrets
2. Verify all secrets are saved
3. Restart the app

### Secrets Not Loading

**Solution**: 
1. Check that secrets are saved in TOML format
2. Verify key names match exactly (case-sensitive)
3. Make sure there are no extra quotes or spaces
4. Restart the app after saving secrets

### Still Not Working?

1. Check the app logs in Streamlit Cloud dashboard
2. Verify your API keys are valid
3. Make sure the secrets file format is correct (TOML, not JSON)

## Local Development

For local development, use a `.env` file (see `.env.example`):

```bash
cp .env.example .env
# Edit .env with your keys
```

The app automatically detects whether it's running locally (uses `.env`) or on Streamlit Cloud (uses `st.secrets`).

