#!/bin/bash

# Comprehensive fix for missing 'gi' module on DGX Spark
# This handles different Ubuntu versions and installation methods

echo "🔧 Comprehensive Fix for Missing 'gi' Module"
echo "============================================"

# Detect Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs)
echo "Detected Ubuntu version: $UBUNTU_VERSION"

# Update package list
echo "1️⃣ Updating package list..."
sudo apt update

# Install PyGObject system packages (method 1)
echo "2️⃣ Installing PyGObject system packages..."
sudo apt install -y \
    python3-gi \
    python3-gi-cairo \
    python3-gi-dev \
    libglib2.0-dev \
    libgirepository1.0-dev \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libatk1.0-dev \
    libgdk-pixbuf2.0-dev \
    libgtk-3-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev

# Install GStreamer packages
echo "3️⃣ Installing GStreamer packages..."
sudo apt install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0

# Try installing PyGObject via pip (method 2)
echo "4️⃣ Trying PyGObject via pip..."
pip3 install --upgrade pip setuptools wheel

# Install PyGObject via pip with specific flags
pip3 install PyGObject --no-cache-dir || {
    echo "PyGObject via pip failed, trying alternative method..."
    
    # Alternative: Install from source
    echo "5️⃣ Installing PyGObject from source..."
    sudo apt install -y \
        meson \
        ninja-build \
        libgirepository1.0-dev \
        libglib2.0-dev \
        libcairo2-dev \
        libpango1.0-dev \
        libatk1.0-dev \
        libgdk-pixbuf2.0-dev \
        libgtk-3-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev
    
    # Try pip install with build dependencies
    pip3 install PyGObject --no-cache-dir --no-binary=:all: || {
        echo "PyGObject installation failed. Trying system package only..."
    }
}

# Install other Python packages
echo "6️⃣ Installing other Python packages..."
pip3 install numpy opencv-python

# Test the gi module
echo "7️⃣ Testing gi module..."
python3 -c "
try:
    import gi
    print('✅ gi module imported successfully')
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    print('✅ GStreamer Python bindings OK')
    Gst.init(None)
    print('✅ GStreamer initialized successfully')
    print('✅ All tests passed!')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "============================================"
    echo "🎉 gi module fix successful!"
    echo "You can now run the consumer locally."
    echo "============================================"
else
    echo "============================================"
    echo "❌ gi module fix failed."
    echo ""
    echo "Manual troubleshooting steps:"
    echo "1. Check Python version: python3 --version"
    echo "2. Check if gi is installed: dpkg -l | grep python3-gi"
    echo "3. Try: sudo apt install --reinstall python3-gi"
    echo "4. Check Python path: python3 -c 'import sys; print(sys.path)'"
    echo "============================================"
fi
