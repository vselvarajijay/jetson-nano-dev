#!/bin/bash

# Check Producer UDP Output
# Run this on Jetson Nano to verify producer is sending UDP packets

echo "📡 Checking Producer UDP Output"
echo "==============================="

echo "1️⃣ Checking if producer is running..."
PRODUCER_PIDS=$(pgrep -f "udp_rtp_producer.py")
if [ -n "$PRODUCER_PIDS" ]; then
    echo "   ✅ Producer process found: $PRODUCER_PIDS"
else
    echo "   ❌ No producer process found"
    echo "   Start producer: ./restart-producer.sh"
    exit 1
fi

echo ""
echo "2️⃣ Checking UDP port 8554..."
if lsof -i :8554 > /dev/null 2>&1; then
    echo "   ✅ UDP port 8554 is active"
    echo "   Port details:"
    lsof -i :8554
else
    echo "   ❌ UDP port 8554 is NOT active"
    echo "   Producer is not sending UDP packets"
fi

echo ""
echo "3️⃣ Testing UDP packet output..."
echo "   Listening for UDP packets for 5 seconds..."

# Start UDP listener
timeout 5 nc -u -l 8555 > /tmp/udp_output.log 2>&1 &
LISTENER_PID=$!

# Wait a moment
sleep 1

# Check if we received any data
if [ -s /tmp/udp_output.log ]; then
    echo "   ✅ UDP packets detected"
    echo "   Sample data:"
    head -3 /tmp/udp_output.log
else
    echo "   ❌ No UDP packets detected"
fi

# Clean up
kill $LISTENER_PID 2>/dev/null || true
rm -f /tmp/udp_output.log

echo ""
echo "4️⃣ Testing producer output with GStreamer..."
echo "   Testing producer pipeline for 3 seconds..."

timeout 3 gst-launch-1.0 -v v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! x264enc tune=zerolatency ! rtph264pay ! udpsink host=0.0.0.0 port=8554 2>&1 | head -10
PRODUCER_TEST_EXIT_CODE=$?

if [ $PRODUCER_TEST_EXIT_CODE -eq 124 ] || [ $PRODUCER_TEST_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Producer pipeline works"
else
    echo "   ❌ Producer pipeline failed"
    echo "   Exit code: $PRODUCER_TEST_EXIT_CODE"
fi

echo ""
echo "5️⃣ Checking producer logs..."
if [ -f "producer.log" ]; then
    echo "   Recent producer log entries:"
    tail -10 producer.log
else
    echo "   ⚠️  No producer.log file found"
fi

echo ""
echo "==============================="
echo "📊 PRODUCER UDP SUMMARY"
echo "==============================="

if [ -n "$PRODUCER_PIDS" ]; then
    echo "✅ Producer process: RUNNING"
else
    echo "❌ Producer process: NOT RUNNING"
fi

if lsof -i :8554 > /dev/null 2>&1; then
    echo "✅ UDP port 8554: ACTIVE"
else
    echo "❌ UDP port 8554: NOT ACTIVE"
fi

if [ $PRODUCER_TEST_EXIT_CODE -eq 124 ] || [ $PRODUCER_TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Producer pipeline: WORKING"
else
    echo "❌ Producer pipeline: FAILED"
fi

echo ""
echo "🎯 NEXT STEPS:"
if [ -z "$PRODUCER_PIDS" ]; then
    echo "1. Start producer: ./restart-producer.sh"
elif ! lsof -i :8554 > /dev/null 2>&1; then
    echo "2. Producer is running but not using UDP port"
    echo "   Check producer logs for errors"
    echo "3. Restart producer: ./restart-producer.sh"
else
    echo "4. Producer appears to be working"
    echo "   Test consumer on DGX Spark"
    echo "   Run: ./debug-consumer-comprehensive.sh on DGX Spark"
fi

echo "==============================="
