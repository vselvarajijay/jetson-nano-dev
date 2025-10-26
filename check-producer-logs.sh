#!/bin/bash

# Check Producer Logs and Status
# Run this on Jetson Nano to verify producer is actually sending data

echo "📊 Producer Logs and Status Check"
echo "================================="

# Check if producer is running
echo "1️⃣ Checking producer process..."
PRODUCER_PIDS=$(pgrep -f "udp_rtp_producer.py")
if [ -n "$PRODUCER_PIDS" ]; then
    echo "   ✅ Producer process found: $PRODUCER_PIDS"
    echo "   Process details:"
    ps aux | grep udp_rtp_producer.py | grep -v grep
else
    echo "   ❌ No producer process found"
    echo "   Producer is NOT running"
    exit 1
fi

echo ""

# Check producer logs
echo "2️⃣ Checking producer logs..."
if [ -f "producer.log" ]; then
    echo "   Recent producer log entries:"
    tail -20 producer.log
else
    echo "   ⚠️  No producer.log file found"
    echo "   Producer might be running without logging"
fi

echo ""

# Check UDP port usage
echo "3️⃣ Checking UDP port 8554..."
if lsof -i :8554 > /dev/null 2>&1; then
    echo "   ✅ UDP port 8554 is active"
    echo "   Port details:"
    lsof -i :8554
else
    echo "   ❌ UDP port 8554 is NOT active"
    echo "   Producer is not sending UDP packets"
fi

echo ""

# Test producer output with netstat
echo "4️⃣ Checking network connections..."
echo "   UDP connections on port 8554:"
netstat -u -n | grep :8554 || echo "   No UDP connections found on port 8554"

echo ""

# Test if producer is actually sending data
echo "5️⃣ Testing producer data output..."
echo "   Running producer test for 3 seconds..."

# Start a simple UDP listener to test if producer is sending
timeout 3 nc -u -l 8555 > /tmp/udp_test.log 2>&1 &
LISTENER_PID=$!

# Wait a moment
sleep 1

# Check if we received any data
if [ -s /tmp/udp_test.log ]; then
    echo "   ✅ Producer is sending UDP data"
    echo "   Sample data received:"
    head -3 /tmp/udp_test.log
else
    echo "   ❌ No UDP data received from producer"
fi

# Clean up
kill $LISTENER_PID 2>/dev/null || true
rm -f /tmp/udp_test.log

echo ""

# Check producer configuration
echo "6️⃣ Checking producer configuration..."
echo "   Producer script location:"
ls -la scripts/udp_rtp_producer.py

echo "   Producer script content (first 20 lines):"
head -20 scripts/udp_rtp_producer.py

echo ""
echo "================================="
echo "📊 PRODUCER STATUS SUMMARY"
echo "================================="

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

if [ -f "producer.log" ]; then
    echo "✅ Producer logs: AVAILABLE"
else
    echo "⚠️  Producer logs: NOT AVAILABLE"
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
    echo "   Check network connectivity from DGX Spark"
    echo "   Run: ./diagnose-network.sh on DGX Spark"
fi

echo "================================="
