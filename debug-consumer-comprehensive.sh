#!/bin/bash

# Comprehensive Consumer Debug Test
# Tests every step of the consumer pipeline

echo "🔍 Comprehensive Consumer Debug Test"
echo "=================================="

JETSON_IP="100.94.31.62"
JETSON_PORT="8554"

echo "Testing with Jetson: $JETSON_IP:$JETSON_PORT"
echo ""

# Test 1: Basic UDP reception
echo "1️⃣ Testing basic UDP reception..."
timeout 5 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! fakesink 2>&1 | head -5
UDP_EXIT_CODE=$?
echo "   Exit code: $UDP_EXIT_CODE"

# Test 2: RTP parsing
echo ""
echo "2️⃣ Testing RTP parsing..."
timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! fakesink 2>&1 | head -5
RTP_EXIT_CODE=$?
echo "   Exit code: $RTP_EXIT_CODE"

# Test 3: H.264 RTP parsing
echo ""
echo "3️⃣ Testing H.264 RTP parsing..."
timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink 2>&1 | head -5
H264_EXIT_CODE=$?
echo "   Exit code: $H264_EXIT_CODE"

# Test 4: Full pipeline
echo ""
echo "4️⃣ Testing full pipeline..."
timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! fakesink 2>&1 | head -5
PIPELINE_EXIT_CODE=$?
echo "   Exit code: $PIPELINE_EXIT_CODE"

# Test 5: Test with appsink (no callback)
echo ""
echo "5️⃣ Testing with appsink (no callback)..."
timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! appsink emit-signals=false 2>&1 | head -5
APPSINK_EXIT_CODE=$?
echo "   Exit code: $APPSINK_EXIT_CODE"

# Test 6: Test with appsink (with callback)
echo ""
echo "6️⃣ Testing with appsink (with callback)..."
timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! appsink emit-signals=true 2>&1 | head -5
APPSINK_CALLBACK_EXIT_CODE=$?
echo "   Exit code: $APPSINK_CALLBACK_EXIT_CODE"

# Test 7: Check if producer is actually sending
echo ""
echo "7️⃣ Checking if producer is actually sending..."
echo "   Producer should be running on Jetson Nano"
echo "   Check producer logs on Jetson Nano"

# Summary
echo ""
echo "=================================="
echo "📊 DEBUG TEST SUMMARY"
echo "=================================="

if [ $UDP_EXIT_CODE -eq 124 ] || [ $UDP_EXIT_CODE -eq 0 ]; then
    echo "✅ UDP reception: OK"
else
    echo "❌ UDP reception: FAILED"
fi

if [ $RTP_EXIT_CODE -eq 124 ] || [ $RTP_EXIT_CODE -eq 0 ]; then
    echo "✅ RTP parsing: OK"
else
    echo "❌ RTP parsing: FAILED"
fi

if [ $H264_EXIT_CODE -eq 124 ] || [ $H264_EXIT_CODE -eq 0 ]; then
    echo "✅ H.264 RTP parsing: OK"
else
    echo "❌ H.264 RTP parsing: FAILED"
fi

if [ $PIPELINE_EXIT_CODE -eq 124 ] || [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    echo "✅ Full pipeline: OK"
else
    echo "❌ Full pipeline: FAILED"
fi

if [ $APPSINK_EXIT_CODE -eq 124 ] || [ $APPSINK_EXIT_CODE -eq 0 ]; then
    echo "✅ Appsink (no callback): OK"
else
    echo "❌ Appsink (no callback): FAILED"
fi

if [ $APPSINK_CALLBACK_EXIT_CODE -eq 124 ] || [ $APPSINK_CALLBACK_EXIT_CODE -eq 0 ]; then
    echo "✅ Appsink (with callback): OK"
else
    echo "❌ Appsink (with callback): FAILED"
fi

echo ""
echo "🎯 ANALYSIS:"

if [ $UDP_EXIT_CODE -ne 124 ] && [ $UDP_EXIT_CODE -ne 0 ]; then
    echo "❌ PRODUCER ISSUE"
    echo "   - No UDP packets received"
    echo "   - Check if producer is running on Jetson Nano"
    echo "   - Run: ./check-producer-status.sh on Jetson Nano"
elif [ $PIPELINE_EXIT_CODE -ne 124 ] && [ $PIPELINE_EXIT_CODE -ne 0 ]; then
    echo "❌ GSTREAMER PIPELINE ISSUE"
    echo "   - UDP packets received but pipeline fails"
    echo "   - Check GStreamer installation"
elif [ $APPSINK_CALLBACK_EXIT_CODE -ne 124 ] && [ $APPSINK_CALLBACK_EXIT_CODE -ne 0 ]; then
    echo "❌ APPSINK CALLBACK ISSUE"
    echo "   - Pipeline works but appsink callback fails"
    echo "   - Issue is in Python consumer code"
else
    echo "✅ EVERYTHING WORKS"
    echo "   - UDP reception: OK"
    echo "   - Pipeline: OK"
    echo "   - Appsink: OK"
    echo "   - Issue is in Python consumer logic"
fi

echo "=================================="
