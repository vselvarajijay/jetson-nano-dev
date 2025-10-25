#!/bin/bash

# RTP Format Analysis Test
# Analyzes the actual RTP format being sent by the producer

echo "🔍 RTP Format Analysis Test"
echo "==========================="

RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}

# Parse URL
if [[ $RTSP_URL =~ ^udp://([^:]+):([0-9]+)$ ]]; then
    HOST=${BASH_REMATCH[1]}
    PORT=${BASH_REMATCH[2]}
else
    echo "❌ Invalid UDP URL format: $RTSP_URL"
    exit 1
fi

echo "🔗 Analyzing RTP stream from: $RTSP_URL"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo ""

# Test 1: Check what RTP caps are available
echo "1️⃣ Checking available RTP caps..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ Received RTP packets (timeout expected)"
else
    echo "   ❌ No RTP packets received"
    exit 1
fi

echo ""

# Test 2: Check H.264 RTP caps with different payload types
echo "2️⃣ Testing H.264 RTP with different payload types..."

for pt in 96 97 98; do
    echo "   Testing payload type $pt..."
    timeout 3 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=$pt ! fakesink 2>&1 | head -5
    
    if [ $? -eq 124 ]; then
        echo "   ✅ Payload type $pt works!"
        WORKING_PT=$pt
        break
    else
        echo "   ❌ Payload type $pt failed"
    fi
done

echo ""

# Test 3: Test without specifying payload type
echo "3️⃣ Testing H.264 RTP without specifying payload type..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ H.264 RTP without PT works (timeout expected)"
    echo "   This means the consumer should work without specifying payload type"
else
    echo "   ❌ H.264 RTP without PT failed"
fi

echo ""

if [ -n "$WORKING_PT" ]; then
    echo "🎯 Found working payload type: $WORKING_PT"
    echo ""
    echo "💡 Solution: Update consumer to use payload type $WORKING_PT"
    echo "   Or make consumer more flexible to handle different payload types"
else
    echo "❌ No working payload type found"
    echo "   The producer might not be sending proper RTP H.264 packets"
fi

echo ""
echo "🔧 Try running the detailed pipeline test:"
echo "   ./debug-udp-pipeline.sh"
