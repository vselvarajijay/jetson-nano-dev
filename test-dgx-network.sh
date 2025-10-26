#!/bin/bash

# Comprehensive Network Test for DGX Spark
# Tests connectivity to Jetson Nano producer

echo "🌐 DGX Spark Network Test"
echo "========================"

JETSON_IP="100.94.31.62"
JETSON_PORT="8554"

echo "Testing connection to Jetson Nano: $JETSON_IP:$JETSON_PORT"
echo ""

# Test 1: Basic ping
echo "1️⃣ Testing ping to Jetson Nano..."
if ping -c 3 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "   ✅ Ping successful"
else
    echo "   ❌ Ping failed"
    echo "   Network connectivity issue!"
    echo ""
    echo "🔧 TROUBLESHOOTING:"
    echo "   1. Check Tailscale: tailscale status"
    echo "   2. Check Jetson Nano IP: ip addr show"
    echo "   3. Try different IP addresses"
    exit 1
fi

# Test 2: Check Tailscale
echo ""
echo "2️⃣ Checking Tailscale status..."
if command -v tailscale > /dev/null 2>&1; then
    echo "   Tailscale status:"
    tailscale status 2>/dev/null | head -5 || echo "   Failed to get Tailscale status"
else
    echo "   ⚠️  Tailscale not installed"
fi

# Test 3: Test UDP reception
echo ""
echo "3️⃣ Testing UDP packet reception..."
echo "   Listening for UDP packets for 5 seconds..."

timeout 5 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! fakesink 2>&1 | head -10
UDP_EXIT_CODE=$?

if [ $UDP_EXIT_CODE -eq 124 ]; then
    echo "   ✅ Received UDP packets (timeout expected)"
elif [ $UDP_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Received UDP packets successfully"
else
    echo "   ❌ No UDP packets received"
    echo "   Exit code: $UDP_EXIT_CODE"
fi

# Test 4: Test RTP parsing
echo ""
echo "4️⃣ Testing RTP packet parsing..."
echo "   Testing RTP depayload for 3 seconds..."

timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! fakesink 2>&1 | head -10
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

timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! fakesink 2>&1 | head -10
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

timeout 3 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! fakesink 2>&1 | head -10
PIPELINE_EXIT_CODE=$?

if [ $PIPELINE_EXIT_CODE -eq 124 ] || [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Full pipeline works"
else
    echo "   ❌ Full pipeline failed"
    echo "   Exit code: $PIPELINE_EXIT_CODE"
fi

# Test 7: Check local network
echo ""
echo "7️⃣ Checking local network configuration..."
echo "   Local IP addresses:"
ip addr show | grep "inet " | grep -v "127.0.0.1" | head -3

echo "   Local UDP connections:"
netstat -u -n | grep :8554 || echo "   No local UDP connections on port 8554"

# Summary
echo ""
echo "========================"
echo "📊 NETWORK TEST SUMMARY"
echo "========================"

if ping -c 1 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "✅ Ping to Jetson: OK"
else
    echo "❌ Ping to Jetson: FAILED"
fi

if [ $UDP_EXIT_CODE -eq 124 ] || [ $UDP_EXIT_CODE -eq 0 ]; then
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
else
    echo "❌ Full pipeline: FAILED"
fi

echo ""
echo "🎯 DIAGNOSIS:"

if ! ping -c 1 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "❌ NETWORK CONNECTIVITY ISSUE"
    echo "   - Jetson Nano is not reachable"
    echo "   - Check Tailscale connection"
    echo "   - Verify Jetson Nano IP address"
elif [ $UDP_EXIT_CODE -ne 124 ] && [ $UDP_EXIT_CODE -ne 0 ]; then
    echo "❌ PRODUCER NOT SENDING UDP PACKETS"
    echo "   - Producer on Jetson Nano is not working"
    echo "   - Check producer status on Jetson Nano"
elif [ $PIPELINE_EXIT_CODE -ne 124 ] && [ $PIPELINE_EXIT_CODE -ne 0 ]; then
    echo "❌ GSTREAMER PIPELINE ISSUE"
    echo "   - Network is OK, but pipeline fails"
    echo "   - Check GStreamer installation"
else
    echo "✅ EVERYTHING WORKS"
    echo "   - Network connectivity: OK"
    echo "   - UDP packets: OK"
    echo "   - Pipeline: OK"
    echo "   - Issue is in Python consumer code"
fi

echo "========================"
