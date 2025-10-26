#!/bin/bash

# Network Connectivity Diagnostic
# Run this on DGX Spark to check connection to Jetson Nano

echo "🌐 Network Connectivity Diagnostic"
echo "================================="

JETSON_IP="100.94.31.62"
JETSON_PORT="8554"

echo "Testing connection to Jetson Nano: $JETSON_IP:$JETSON_PORT"
echo ""

# Test 1: Basic ping
echo "1️⃣ Testing basic ping..."
if ping -c 3 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "   ✅ Ping to $JETSON_IP successful"
else
    echo "   ❌ Ping to $JETSON_IP failed"
    echo "   This indicates a network connectivity issue"
    echo ""
    echo "🔧 TROUBLESHOOTING STEPS:"
    echo "   1. Check if Tailscale is running on both machines"
    echo "   2. Verify Jetson Nano IP address"
    echo "   3. Check firewall settings"
    echo "   4. Try: tailscale status"
    exit 1
fi

# Test 2: Check Tailscale status
echo ""
echo "2️⃣ Checking Tailscale status..."
if command -v tailscale > /dev/null 2>&1; then
    echo "   Tailscale status:"
    tailscale status 2>/dev/null | head -5 || echo "   Failed to get Tailscale status"
else
    echo "   ⚠️  Tailscale command not found"
fi

# Test 3: Check local IP
echo ""
echo "3️⃣ Checking local network configuration..."
echo "   Local IP addresses:"
ip addr show | grep "inet " | grep -v "127.0.0.1" | head -3

# Test 4: Test UDP port accessibility
echo ""
echo "4️⃣ Testing UDP port accessibility..."
echo "   Testing UDP port $JETSON_PORT..."

# Use netcat to test UDP port
timeout 3 nc -uz -w 1 "$JETSON_IP" "$JETSON_PORT" 2>&1
NC_EXIT_CODE=$?

if [ $NC_EXIT_CODE -eq 0 ]; then
    echo "   ✅ UDP port $JETSON_PORT is accessible"
elif [ $NC_EXIT_CODE -eq 124 ]; then
    echo "   ⚠️  UDP port test timed out (this is normal for UDP)"
else
    echo "   ❌ UDP port $JETSON_PORT test failed"
    echo "   Exit code: $NC_EXIT_CODE"
fi

# Test 5: Test with different IP addresses
echo ""
echo "5️⃣ Testing alternative IP addresses..."

# Try common Tailscale IP ranges
for IP in "100.94.31.62" "192.168.0.237" "10.0.0.100"; do
    echo "   Testing $IP..."
    if ping -c 1 -W 1 "$IP" > /dev/null 2>&1; then
        echo "   ✅ $IP is reachable"
    else
        echo "   ❌ $IP is not reachable"
    fi
done

# Test 6: Check if producer is actually sending
echo ""
echo "6️⃣ Testing if producer is sending UDP packets..."
echo "   Listening for UDP packets for 5 seconds..."

timeout 5 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! fakesink 2>&1 | head -10
GST_EXIT_CODE=$?

if [ $GST_EXIT_CODE -eq 124 ]; then
    echo "   ✅ Received UDP packets (timeout expected)"
elif [ $GST_EXIT_CODE -eq 0 ]; then
    echo "   ✅ Received UDP packets successfully"
else
    echo "   ❌ No UDP packets received"
    echo "   Exit code: $GST_EXIT_CODE"
fi

# Summary
echo ""
echo "================================="
echo "📊 NETWORK DIAGNOSTIC SUMMARY"
echo "================================="

if ping -c 1 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "✅ Basic connectivity: OK"
else
    echo "❌ Basic connectivity: FAILED"
fi

if [ $GST_EXIT_CODE -eq 124 ] || [ $GST_EXIT_CODE -eq 0 ]; then
    echo "✅ UDP packet reception: OK"
else
    echo "❌ UDP packet reception: FAILED"
fi

echo ""
echo "🎯 LIKELY ISSUES:"
if ! ping -c 1 -W 1 "$JETSON_IP" > /dev/null 2>&1; then
    echo "1. ❌ Network connectivity issue"
    echo "   - Check Tailscale connection"
    echo "   - Verify Jetson Nano IP address"
    echo "   - Check firewall settings"
elif [ $GST_EXIT_CODE -ne 124 ] && [ $GST_EXIT_CODE -ne 0 ]; then
    echo "2. ❌ Producer not sending UDP packets"
    echo "   - Check if producer is running on Jetson Nano"
    echo "   - Run: ./check-producer-status.sh on Jetson Nano"
else
    echo "3. ✅ Network and UDP are working"
    echo "   - Issue might be in consumer Python code"
    echo "   - Check consumer logs for errors"
fi

echo "================================="
