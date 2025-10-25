#!/bin/bash

# Detailed UDP Pipeline Debug Test
# Tests each step of the consumer pipeline to find the failure point

echo "🔍 Detailed UDP Pipeline Debug Test"
echo "==================================="

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
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ Received UDP packets (timeout expected)"
else
    echo "   ❌ No UDP packets received"
    echo "   This means the producer isn't sending data or network issue"
    exit 1
fi

echo ""

# Test 2: RTP packet reception with caps
echo "2️⃣ Testing RTP packet reception with caps..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ Received RTP packets (timeout expected)"
else
    echo "   ❌ RTP caps filtering failed"
    echo "   This means the RTP format doesn't match expected caps"
    exit 1
fi

echo ""

# Test 3: RTP depayloader
echo "3️⃣ Testing RTP H.264 depayloader..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ RTP depayloader works (timeout expected)"
else
    echo "   ❌ RTP depayloader failed"
    echo "   This means the RTP H.264 format is incorrect"
    exit 1
fi

echo ""

# Test 4: H.264 parser
echo "4️⃣ Testing H.264 parser..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ H.264 parser works (timeout expected)"
else
    echo "   ❌ H.264 parser failed"
    echo "   This means the H.264 stream format is incorrect"
    exit 1
fi

echo ""

# Test 5: H.264 decoder
echo "5️⃣ Testing H.264 decoder..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! avdec_h264 ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! avdec_h264 ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ H.264 decoder works (timeout expected)"
else
    echo "   ❌ H.264 decoder failed"
    echo "   This means the H.264 stream cannot be decoded"
    exit 1
fi

echo ""

# Test 6: Full pipeline with video conversion
echo "6️⃣ Testing full pipeline with video conversion..."
echo "   Command: gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! fakesink"
timeout 5 gst-launch-1.0 udpsrc port=$PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! fakesink 2>&1 | head -10

if [ $? -eq 124 ]; then
    echo "   ✅ Full pipeline works (timeout expected)"
    echo ""
    echo "🎉 All pipeline tests passed!"
    echo "The issue might be with the Python consumer script or appsink configuration."
else
    echo "   ❌ Full pipeline failed"
    echo "   This means there's an issue with video conversion or the complete pipeline"
fi

echo ""
echo "💡 Next steps:"
echo "   1. If all tests pass, the issue is in the Python consumer script"
echo "   2. If any test fails, check the producer's RTP/H.264 format"
echo "   3. Try running the consumer with GST_DEBUG=3 for more details"
