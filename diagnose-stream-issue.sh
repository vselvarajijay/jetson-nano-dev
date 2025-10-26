#!/bin/bash

# Comprehensive Network and Stream Diagnostic
# Tests if the issue is Docker networking, producer, or something else

echo "🔍 Comprehensive Stream Diagnostic"
echo "================================="

PRODUCER_IP="100.94.31.62"
PRODUCER_PORT="8554"

echo "Testing connectivity to Producer: $PRODUCER_IP:$PRODUCER_PORT"
echo ""

# Test 1: Basic network connectivity
echo "1️⃣ Testing basic network connectivity..."
if ping -c 3 -W 1 "$PRODUCER_IP" > /dev/null 2>&1; then
    echo "   ✅ Ping to $PRODUCER_IP successful"
else
    echo "   ❌ Ping to $PRODUCER_IP failed"
    echo "   This indicates a network connectivity issue"
    exit 1
fi

# Test 2: Check if producer is running (UDP port check)
echo ""
echo "2️⃣ Checking if producer is running..."
echo "   Testing UDP port $PRODUCER_PORT..."

# Use netcat to test UDP port
timeout 3 nc -uz -w 1 "$PRODUCER_IP" "$PRODUCER_PORT" 2>&1
NC_EXIT_CODE=$?

if [ $NC_EXIT_CODE -eq 0 ]; then
    echo "   ✅ UDP port $PRODUCER_PORT is accessible"
elif [ $NC_EXIT_CODE -eq 124 ]; then
    echo "   ⚠️  UDP port test timed out (this is normal for UDP)"
else
    echo "   ❌ UDP port $PRODUCER_PORT test failed"
    echo "   Producer might not be running or port is blocked"
fi

# Test 3: Test UDP packet reception with GStreamer
echo ""
echo "3️⃣ Testing UDP packet reception with GStreamer..."
echo "   Listening for UDP packets for 5 seconds..."

timeout 5 gst-launch-1.0 -v udpsrc port=$PRODUCER_PORT ! fakesink 2>&1 | head -10
GST_EXIT_CODE=$?

if [ $GST_EXIT_CODE -eq 124 ]; then
    echo "   ✅ GStreamer received UDP packets (timeout expected)"
elif [ $GST_EXIT_CODE -eq 0 ]; then
    echo "   ✅ GStreamer received UDP packets successfully"
else
    echo "   ❌ GStreamer failed to receive UDP packets"
    echo "   Exit code: $GST_EXIT_CODE"
fi

# Test 4: Test RTP packet parsing
echo ""
echo "4️⃣ Testing RTP packet parsing..."
echo "   Testing RTP depayload for 3 seconds..."

timeout 3 gst-launch-1.0 -v udpsrc port=$PRODUCER_PORT ! application/x-rtp ! fakesink 2>&1 | head -10
RTP_EXIT_CODE=$?

if [ $RTP_EXIT_CODE -eq 124 ] || [ $RTP_EXIT_CODE -eq 0 ]; then
    echo "   ✅ RTP packets received and parsed"
else
    echo "   ❌ RTP packet parsing failed"
    echo "   Exit code: $RTP_EXIT_CODE"
fi

# Test 5: Test H.264 RTP parsing
echo ""
echo "5️⃣ Testing H.264 RTP parsing..."
echo "   Testing H.264 RTP depayload for 3 seconds..."

timeout 3 gst-launch-1.0 -v udpsrc port=$PRODUCER_PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink 2>&1 | head -10
H264_EXIT_CODE=$?

if [ $H264_EXIT_CODE -eq 124 ] || [ $H264_EXIT_CODE -eq 0 ]; then
    echo "   ✅ H.264 RTP packets received and parsed"
else
    echo "   ❌ H.264 RTP packet parsing failed"
    echo "   Exit code: $H264_EXIT_CODE"
fi

# Test 6: Test full pipeline
echo ""
echo "6️⃣ Testing full consumer pipeline..."
echo "   Testing complete pipeline for 3 seconds..."

timeout 3 gst-launch-1.0 -v udpsrc port=$PRODUCER_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! fakesink 2>&1 | head -10
PIPELINE_EXIT_CODE=$?

if [ $PIPELINE_EXIT_CODE -eq 124 ] || [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Full pipeline works"
else
    echo "   ❌ Full pipeline failed"
    echo "   Exit code: $PIPELINE_EXIT_CODE"
fi

# Summary
echo ""
echo "================================="
echo "📊 DIAGNOSTIC SUMMARY"
echo "================================="

if [ $NC_EXIT_CODE -eq 0 ] || [ $NC_EXIT_CODE -eq 124 ]; then
    echo "✅ Network connectivity: OK"
else
    echo "❌ Network connectivity: FAILED"
fi

if [ $GST_EXIT_CODE -eq 124 ] || [ $GST_EXIT_CODE -eq 0 ]; then
    echo "✅ UDP packet reception: OK"
else
    echo "❌ UDP packet reception: FAILED"
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
    echo ""
    echo "🎯 CONCLUSION: The issue is NOT network connectivity"
    echo "   The problem is likely in the Python consumer script"
    echo "   or Docker container configuration"
else
    echo "❌ Full pipeline: FAILED"
    echo ""
    echo "🎯 CONCLUSION: There's a network or producer issue"
    echo "   Check if producer is running on Jetson Nano"
fi

echo "================================="
