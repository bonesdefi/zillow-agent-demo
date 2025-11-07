#!/bin/bash
# Script to help set up .env file with API keys

echo "======================================"
echo "Environment Setup Helper"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ .env file created"
    else
        echo "⚠️  .env.example not found, creating basic .env file..."
        cat > .env << EOF
# Anthropic API Key (for Claude AI)
# Get from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# RapidAPI Key (for Zillow data)
# Get from: https://rapidapi.com/marketplace/api/real-time-zillow-data
RAPIDAPI_KEY=your_rapidapi_key_here

# API Configuration
ZILLOW_API_BASE_URL=https://real-time-zillow-data.p.rapidapi.com
ZILLOW_API_HOST=real-time-zillow-data.p.rapidapi.com
EOF
        echo "✅ .env file created with template"
    fi
else
    echo "✅ .env file already exists"
fi

echo ""
echo "Please edit .env and add your actual API keys:"
echo "  - ANTHROPIC_API_KEY"
echo "  - RAPIDAPI_KEY"
echo ""
echo "Then verify with: python3 check_env.py"

