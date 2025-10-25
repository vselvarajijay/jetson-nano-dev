#!/bin/bash

# Install required packages for RTSP Consumer on DGX Spark
# Run this script on the DGX Spark system

echo "🔧 Installing RTSP Consumer Dependencies on DGX Spark"
echo "=================================================="

# Update package list
echo "1️⃣ Updating package list..."
sudo apt update

# Install system packages
echo "2️⃣ Installing system packages..."
sudo apt install -y \
    python3-pip \
    python3-dev \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    libgstreamer-plugins-good1.0-dev

# Install Python packages
echo "3️⃣ Installing Python packages..."
pip3 install --upgrade pip
pip3 install \
    numpy \
    opencv-python \
    Pillow \
    psutil \
    requests

# Test installation
echo "4️⃣ Testing installation..."
python3 -c "
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)
print('✅ GStreamer Python bindings OK')

import cv2
print(f'✅ OpenCV version: {cv2.__version__}')

import numpy as np
print(f'✅ NumPy version: {np.__version__}')

print('✅ All packages installed successfully!')
"

echo "=================================================="
echo "🎉 Installation complete! You can now run the consumer locally."
echo "=================================================="
