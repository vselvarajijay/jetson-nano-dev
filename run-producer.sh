#!/bin/bash

echo "🚀 Starting Simple DeepStream Producer..."
echo "=========================================="

# Kill any existing producers
echo "Checking for existing processes..."
pkill -f udp_rtp_producer.py 2>/dev/null
sleep 1

# Check camera
if [ ! -e "/dev/video4" ]; then
    echo "❌ Camera /dev/video4 not found!"
    exit 1
fi

echo "✅ Camera found"

# Run producer
echo "Starting producer..."
python3 producer/udp_rtp_producer.py