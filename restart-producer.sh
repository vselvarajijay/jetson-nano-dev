#!/bin/bash

# Quick Producer Restart Script
# Run this on Jetson Nano to restart the producer

echo "🚀 Quick Producer Restart"
echo "========================"

# Kill any existing producer processes
echo "1️⃣ Killing existing producer processes..."
pkill -f "udp_rtp_producer.py" 2>/dev/null || echo "   No existing processes found"
sleep 2

# Check if camera is available
echo "2️⃣ Checking camera availability..."
if [ ! -e "/dev/video4" ]; then
    echo "   ❌ Camera /dev/video4 not found"
    echo "   Available video devices:"
    ls -la /dev/video* 2>/dev/null || echo "   No video devices found"
    exit 1
fi

if lsof /dev/video4 > /dev/null 2>&1; then
    echo "   ⚠️  Camera /dev/video4 is busy"
    echo "   Killing processes using camera..."
    lsof -t /dev/video4 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "   ✅ Camera /dev/video4 is available"

# Start the producer
echo "3️⃣ Starting producer..."
echo "   Running: python3 scripts/udp_rtp_producer.py"

# Run producer in background
nohup python3 scripts/udp_rtp_producer.py > producer.log 2>&1 &
PRODUCER_PID=$!

echo "   Producer started with PID: $PRODUCER_PID"

# Wait a moment for producer to start
sleep 3

# Check if producer is running
echo "4️⃣ Verifying producer is running..."
if ps -p $PRODUCER_PID > /dev/null; then
    echo "   ✅ Producer is running (PID: $PRODUCER_PID)"
    
    # Check if UDP port is being used
    if lsof -i :8554 > /dev/null 2>&1; then
        echo "   ✅ UDP port 8554 is active"
        echo "   Producer is sending UDP packets"
    else
        echo "   ⚠️  UDP port 8554 not active yet"
        echo "   Producer might still be starting..."
    fi
else
    echo "   ❌ Producer failed to start"
    echo "   Check producer.log for errors:"
    tail -10 producer.log 2>/dev/null || echo "   No log file found"
fi

echo ""
echo "========================"
echo "📊 PRODUCER STATUS"
echo "========================"

if ps -p $PRODUCER_PID > /dev/null 2>&1; then
    echo "✅ Producer: RUNNING (PID: $PRODUCER_PID)"
    echo "✅ Log file: producer.log"
    echo "✅ UDP port: 8554"
    echo ""
    echo "🎯 Producer should now be streaming to DGX Spark"
    echo "   Test consumer on DGX Spark now"
else
    echo "❌ Producer: FAILED TO START"
    echo "   Check producer.log for errors"
fi

echo "========================"
