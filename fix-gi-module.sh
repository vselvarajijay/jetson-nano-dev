#!/bin/bash

# Quick fix for missing 'gi' module on DGX Spark
# Run this script on the DGX Spark system

echo "🔧 Quick Fix for Missing 'gi' Module"
echo "===================================="

# Update package list
echo "1️⃣ Updating package list..."
sudo apt update

# Install PyGObject and dependencies
echo "2️⃣ Installing PyGObject and dependencies..."
sudo apt install -y \
    python3-gi \
    python3-gi-cairo \
    libglib2.0-dev \
    libgirepository1.0-dev \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libatk1.0-dev \
    libgdk-pixbuf2.0-dev \
    libgtk-3-dev

# Install GStreamer Python bindings
echo "3️⃣ Installing GStreamer Python bindings..."
sudo apt install -y \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Install Python packages
echo "4️⃣ Installing Python packages..."
pip3 install --upgrade pip
pip3 install numpy opencv-python

# Test the gi module
echo "5️⃣ Testing gi module..."
python3 -c "
import gi
print('✅ gi module imported successfully')
gi.require_version('Gst', '1.0')
from gi.repository import Gst
print('✅ GStreamer Python bindings OK')
Gst.init(None)
print('✅ GStreamer initialized successfully')
"

if [ $? -eq 0 ]; then
    echo "===================================="
    echo "🎉 gi module fix successful!"
    echo "You can now run the consumer locally."
    echo "===================================="
else
    echo "===================================="
    echo "❌ gi module fix failed."
    echo "Try running the full installation script."
    echo "===================================="
fi
