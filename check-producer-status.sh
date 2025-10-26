#!/bin/bash

# Check Producer Status on Jetson Nano
# Run this script on the Jetson Nano to verify producer is running

echo "🔍 Checking Producer Status on Jetson Nano"
echo "=========================================="

# Check if producer process is running
echo "1️⃣ Checking if producer process is running..."
PRODUCER_PIDS=$(pgrep -f "udp_rtp_producer.py")
if [ -n "$PRODUCER_PIDS" ]; then
    echo "   ✅ Producer process found: $PRODUCER_PIDS"
    echo "   Process details:"
    ps aux | grep udp_rtp_producer.py | grep -v grep
else
    echo "   ❌ No producer process found"
    echo "   Producer is NOT running"
fi

echo ""

# Check if camera is available
echo "2️⃣ Checking camera availability..."
if [ -e "/dev/video4" ]; then
    echo "   ✅ Camera device /dev/video4 exists"
    if lsof /dev/video4 > /dev/null 2>&1; then
        echo "   ✅ Camera is being used (good)"
    else
        echo "   ⚠️  Camera is not being used"
    fi
else
    echo "   ❌ Camera device /dev/video4 not found"
fi

echo ""

# Check if UDP port is being used
echo "3️⃣ Checking UDP port 8554..."
if lsof -i :8554 > /dev/null 2>&1; then
    echo "   ✅ UDP port 8554 is in use"
    echo "   Port details:"
    lsof -i :8554
else
    echo "   ❌ UDP port 8554 is NOT in use"
    echo "   Producer is not sending UDP packets"
fi

echo ""

# Test basic GStreamer pipeline
echo "4️⃣ Testing basic GStreamer pipeline..."
echo "   Testing camera capture for 3 seconds..."

timeout 3 gst-launch-1.0 v4l2src device=/dev/video4 ! fakesink 2>&1 | head -5
CAMERA_EXIT_CODE=$?

if [ $CAMERA_EXIT_CODE -eq 124 ] || [ $CAMERA_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Camera capture works"
else
    echo "   ❌ Camera capture failed"
    echo "   Exit code: $CAMERA_EXIT_CODE"
fi

echo ""

# Test UDP streaming pipeline
echo "5️⃣ Testing UDP streaming pipeline..."
echo "   Testing UDP streaming for 3 seconds..."

timeout 3 gst-launch-1.0 v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! x264enc tune=zerolatency ! rtph264pay ! udpsink host=0.0.0.0 port=8554 2>&1 | head -5
UDP_EXIT_CODE=$?

if [ $UDP_EXIT_CODE -eq 124 ] || [ $UDP_EXIT_CODE -eq 0 ]; then
    echo "   ✅ UDP streaming pipeline works"
else
    echo "   ❌ UDP streaming pipeline failed"
    echo "   Exit code: $UDP_EXIT_CODE"
fi

echo ""

# Check network connectivity to DGX Spark
echo "6️⃣ Checking network connectivity to DGX Spark..."
DGX_IP="100.94.31.62"  # Replace with actual DGX IP if different

if ping -c 3 -W 1 "$DGX_IP" > /dev/null 2>&1; then
    echo "   ✅ Can reach DGX Spark ($DGX_IP)"
else
    echo "   ❌ Cannot reach DGX Spark ($DGX_IP)"
    echo "   Check Tailscale connection"
fi

echo ""
echo "=========================================="
echo "📊 PRODUCER STATUS SUMMARY"
echo "=========================================="

if [ -n "$PRODUCER_PIDS" ]; then
    echo "✅ Producer process: RUNNING"
else
    echo "❌ Producer process: NOT RUNNING"
    echo "   Solution: Run ./run-producer.sh"
fi

if lsof -i :8554 > /dev/null 2>&1; then
    echo "✅ UDP port 8554: IN USE"
else
    echo "❌ UDP port 8554: NOT IN USE"
    echo "   Solution: Start producer"
fi

if [ $CAMERA_EXIT_CODE -eq 124 ] || [ $CAMERA_EXIT_CODE -eq 0 ]; then
    echo "✅ Camera: WORKING"
else
    echo "❌ Camera: NOT WORKING"
fi

if [ $UDP_EXIT_CODE -eq 124 ] || [ $UDP_EXIT_CODE -eq 0 ]; then
    echo "✅ UDP streaming: WORKING"
else
    echo "❌ UDP streaming: NOT WORKING"
fi

echo ""
echo "🎯 NEXT STEPS:"
if [ -z "$PRODUCER_PIDS" ]; then
    echo "1. Start producer: ./run-producer.sh"
fi
if ! lsof -i :8554 > /dev/null 2>&1; then
    echo "2. Check producer is sending UDP packets"
fi
echo "3. Test consumer on DGX Spark"
echo "=========================================="
