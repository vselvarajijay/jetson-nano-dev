#!/bin/bash

# Test UDP Packet Transmission
# Run this on Jetson Nano to verify UDP packets are being sent

echo "📡 Testing UDP Packet Transmission"
echo "================================="

echo "1️⃣ Starting UDP listener on port 8555..."
echo "   (This will listen for UDP packets for 10 seconds)"

# Start UDP listener in background
timeout 10 nc -u -l 8555 > /tmp/udp_test.log 2>&1 &
LISTENER_PID=$!

echo "2️⃣ Testing UDP packet transmission..."
echo "   Sending test packets to localhost:8555"

# Send test UDP packets
for i in {1..5}; do
    echo "Test packet $i" | nc -u localhost 8555
    sleep 1
done

# Wait for listener to finish
wait $LISTENER_PID

echo "3️⃣ Checking if packets were received..."
if [ -s /tmp/udp_test.log ]; then
    echo "   ✅ UDP packets received:"
    cat /tmp/udp_test.log
else
    echo "   ❌ No UDP packets received"
fi

echo ""
echo "4️⃣ Testing producer UDP output..."
echo "   Starting UDP listener on port 8554 for 5 seconds..."

# Start UDP listener for producer port
timeout 5 nc -u -l 8554 > /tmp/producer_udp.log 2>&1 &
PRODUCER_LISTENER_PID=$!

# Wait for listener to finish
wait $PRODUCER_LISTENER_PID

echo "5️⃣ Checking producer UDP output..."
if [ -s /tmp/producer_udp.log ]; then
    echo "   ✅ Producer UDP packets detected:"
    head -5 /tmp/producer_udp.log
    echo "   Total bytes received: $(wc -c < /tmp/producer_udp.log)"
else
    echo "   ❌ No producer UDP packets detected"
    echo "   Producer is not sending UDP packets"
fi

# Clean up
rm -f /tmp/udp_test.log /tmp/producer_udp.log

echo ""
echo "================================="
echo "📊 UDP TRANSMISSION SUMMARY"
echo "================================="

if [ -s /tmp/producer_udp.log ]; then
    echo "✅ Producer UDP: WORKING"
    echo "   Bytes received: $(wc -c < /tmp/producer_udp.log)"
else
    echo "❌ Producer UDP: NOT WORKING"
    echo "   Producer is not sending UDP packets"
fi

echo "================================="
