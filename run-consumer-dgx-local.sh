#!/bin/bash

# Run RTSP Consumer on DGX Spark (local, not Docker)
# This script should be run on the DGX Spark system

echo "🚀 Starting RTSP Consumer on DGX Spark (Local)"
echo "=============================================="

# Set environment variables
export PYTHONUNBUFFERED=1
export RTSP_URL="udp://100.94.31.62:8554"

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python3 -c "
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    print('✅ GStreamer Python bindings OK')
except ImportError as e:
    print(f'❌ GStreamer Python bindings missing: {e}')
    print('Run: ./install-dgx-packages.sh')
    exit(1)

try:
    import cv2
    print(f'✅ OpenCV version: {cv2.__version__}')
except ImportError as e:
    print(f'❌ OpenCV missing: {e}')
    print('Run: ./install-dgx-packages.sh')
    exit(1)

try:
    import numpy as np
    print(f'✅ NumPy version: {np.__version__}')
except ImportError as e:
    print(f'❌ NumPy missing: {e}')
    print('Run: ./install-dgx-packages.sh')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Please install them first."
    exit 1
fi

echo "✅ All dependencies OK"
echo ""

# Check if producer is running
echo "🔍 Checking if producer is running..."
if ping -c 1 -W 1 100.94.31.62 > /dev/null 2>&1; then
    echo "✅ Jetson Nano (100.94.31.62) is reachable"
else
    echo "❌ Jetson Nano (100.94.31.62) is not reachable"
    echo "   Check Tailscale connection or producer status"
    exit 1
fi

echo ""
echo "🎥 Starting consumer..."
echo "Stream URL: $RTSP_URL"
echo "Press Ctrl+C to stop"
echo ""

# Run the consumer
python3 scripts/rtsp_consumer.py
