#!/bin/bash

# Simple UDP Stream Test
# Tests if UDP packets are reaching the consumer

echo "🧪 Testing UDP Stream Reception"
echo "==============================="

RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}

# Parse URL
if [[ $RTSP_URL =~ ^udp://([^:]+):([0-9]+)$ ]]; then
    HOST=${BASH_REMATCH[1]}
    PORT=${BASH_REMATCH[2]}
else
    echo "❌ Invalid UDP URL format: $RTSP_URL"
    exit 1
fi

echo "🔗 Testing URL: $RTSP_URL"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo ""

# Test 1: Basic UDP reception
echo "1️⃣ Testing basic UDP packet reception..."
timeout 10 gst-launch-1.0 udpsrc port=$PORT ! fakesink

if [ $? -eq 124 ]; then
    echo "   ✅ Received UDP packets (timeout expected)"
else
    echo "   ❌ No UDP packets received"
fi

echo ""

# Test 2: RTP packet reception
echo "2️⃣ Testing RTP packet reception..."
timeout 10 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink

if [ $? -eq 124 ]; then
    echo "   ✅ Received RTP packets (timeout expected)"
else
    echo "   ❌ No RTP packets received"
fi

echo ""

# Test 3: Full pipeline test
echo "3️⃣ Testing full consumer pipeline..."
timeout 10 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! fakesink

if [ $? -eq 124 ]; then
    echo "   ✅ Full pipeline works (timeout expected)"
else
    echo "   ❌ Full pipeline failed"
fi

echo ""
echo "💡 If all tests fail, check:"
echo "   1. Producer is running on Jetson Nano"
echo "   2. Network connectivity between DGX Spark and Jetson"
echo "   3. Firewall settings"
echo "   4. Producer is actually sending UDP packets"
