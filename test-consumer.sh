#!/bin/bash

# Test script for consumer

echo "🧪 Testing UDP consumer with grayscale stream"
echo "=============================================="

# Test command
gst-launch-1.0 -v udpsrc port=8554 address=0.0.0.0 ! \
    application/x-rtp,encoding-name=H264,payload=96 ! \
    rtph264depay ! \
    h264parse ! \
    avdec_h264 ! \
    videoconvert ! \
    video/x-raw,format=GRAY8 ! \
    videoconvert ! \
    video/x-raw,format=BGR ! \
    autovideosink sync=false

echo "✅ Consumer test complete"

