#!/bin/bash

# Consumer Test Script
# Tests different URLs to find the working connection

echo "🎥 Consumer Connection Test"
echo "=========================="

# Test URLs
TAILSCALE_URL="udp://100.94.31.62:8554"
WIFI_URL="udp://192.168.0.237:8554"
LOCAL_URL="udp://127.0.0.1:8554"

echo "Testing different connection URLs..."
echo ""

# Test 1: Tailscale URL
echo "1️⃣ Testing Tailscale URL: $TAILSCALE_URL"
echo "   Setting RTSP_URL=$TAILSCALE_URL"
export RTSP_URL="$TAILSCALE_URL"
timeout 10 python3 scripts/rtsp_consumer.py
if [ $? -eq 124 ]; then
    echo "   ✅ Tailscale URL works!"
    exit 0
else
    echo "   ❌ Tailscale URL failed"
fi

echo ""

# Test 2: WiFi URL
echo "2️⃣ Testing WiFi URL: $WIFI_URL"
echo "   Setting RTSP_URL=$WIFI_URL"
export RTSP_URL="$WIFI_URL"
timeout 10 python3 scripts/rtsp_consumer.py
if [ $? -eq 124 ]; then
    echo "   ✅ WiFi URL works!"
    exit 0
else
    echo "   ❌ WiFi URL failed"
fi

echo ""

# Test 3: Local URL (if producer is running locally)
echo "3️⃣ Testing Local URL: $LOCAL_URL"
echo "   Setting RTSP_URL=$LOCAL_URL"
export RTSP_URL="$LOCAL_URL"
timeout 10 python3 scripts/rtsp_consumer.py
if [ $? -eq 124 ]; then
    echo "   ✅ Local URL works!"
    exit 0
else
    echo "   ❌ Local URL failed"
fi

echo ""
echo "❌ All URLs failed. Check:"
echo "   1. Producer is running on Jetson Nano"
echo "   2. Network connectivity between DGX Spark and Jetson"
echo "   3. Firewall settings"
echo "   4. Producer is actually streaming data"
