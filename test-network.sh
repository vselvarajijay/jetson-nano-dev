#!/bin/bash

# Network Connectivity Test Script
# Tests connection from DGX Spark to Jetson Nano

echo "🔍 Network Connectivity Test"
echo "============================"

# Test IP addresses
JETSON_TAILSCALE_IP="100.94.31.62"
JETSON_WIFI_IP="192.168.0.237"
UDP_PORT="8554"

echo "Testing connectivity to Jetson Nano..."
echo ""

# Test 1: Ping Tailscale IP
echo "1️⃣ Testing Tailscale IP: $JETSON_TAILSCALE_IP"
if ping -c 3 $JETSON_TAILSCALE_IP >/dev/null 2>&1; then
    echo "   ✅ Ping successful"
else
    echo "   ❌ Ping failed"
fi

# Test 2: Ping WiFi IP (if on same network)
echo "2️⃣ Testing WiFi IP: $JETSON_WIFI_IP"
if ping -c 3 $JETSON_WIFI_IP >/dev/null 2>&1; then
    echo "   ✅ Ping successful"
else
    echo "   ❌ Ping failed (expected if not on same network)"
fi

# Test 3: UDP port connectivity
echo "3️⃣ Testing UDP port $UDP_PORT on Tailscale IP..."
if timeout 3 nc -u -z $JETSON_TAILSCALE_IP $UDP_PORT 2>/dev/null; then
    echo "   ✅ UDP port accessible"
else
    echo "   ❌ UDP port not accessible"
fi

# Test 4: UDP port connectivity on WiFi IP
echo "4️⃣ Testing UDP port $UDP_PORT on WiFi IP..."
if timeout 3 nc -u -z $JETSON_WIFI_IP $UDP_PORT 2>/dev/null; then
    echo "   ✅ UDP port accessible"
else
    echo "   ❌ UDP port not accessible"
fi

# Test 5: GStreamer UDP test
echo "5️⃣ Testing GStreamer UDP reception..."
echo "   Testing Tailscale IP..."
timeout 5 gst-launch-1.0 udpsrc port=8554 ! application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 ! rtph264depay ! fakesink >/dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "   ✅ GStreamer received data from Tailscale IP"
else
    echo "   ❌ GStreamer failed to receive data from Tailscale IP"
fi

echo ""
echo "🎯 Recommended URLs to test:"
echo "   Tailscale: udp://$JETSON_TAILSCALE_IP:$UDP_PORT"
echo "   WiFi:      udp://$JETSON_WIFI_IP:$UDP_PORT"
echo ""
echo "💡 If Tailscale fails, try WiFi IP if both devices are on same network"
