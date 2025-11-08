#!/bin/bash
# Script to copy the Streamlit UI screenshot to the docs/images directory

SOURCE_FILE=""
TARGET_DIR="docs/images"
TARGET_FILE="$TARGET_DIR/streamlit-ui-screenshot.png"

# Try to find the source file in common locations
if [ -f "$HOME/Downloads/real-estate-ai-assistant(1).png" ]; then
    SOURCE_FILE="$HOME/Downloads/real-estate-ai-assistant(1).png"
elif [ -f "$HOME/Desktop/real-estate-ai-assistant(1).png" ]; then
    SOURCE_FILE="$HOME/Desktop/real-estate-ai-assistant(1).png"
elif [ -f "/Users/michaelpento.lv/real-estate-ai-assistant(1).png" ]; then
    SOURCE_FILE="/Users/michaelpento.lv/real-estate-ai-assistant(1).png"
fi

# If not found, prompt user
if [ -z "$SOURCE_FILE" ]; then
    echo "Image file not found in common locations."
    echo "Please run:"
    echo "  cp /path/to/real-estate-ai-assistant\\(1\\).png $TARGET_FILE"
    echo ""
    echo "Or if you know the exact path, specify it:"
    read -p "Enter full path to image file: " SOURCE_FILE
fi

# Copy the file
if [ -f "$SOURCE_FILE" ]; then
    mkdir -p "$TARGET_DIR"
    cp "$SOURCE_FILE" "$TARGET_FILE"
    echo "✅ Copied image to $TARGET_FILE"
    echo "File size: $(ls -lh "$TARGET_FILE" | awk '{print $5}')"
else
    echo "❌ Error: Source file not found: $SOURCE_FILE"
    exit 1
fi

