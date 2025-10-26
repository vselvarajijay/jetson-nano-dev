#!/bin/bash

# Check Jetson Nano IP Address
# Run this on Jetson Nano to get current IP addresses

echo "🔍 Jetson Nano IP Address Check"
echo "=============================="

echo "1️⃣ Current IP addresses:"
echo "   All network interfaces:"
ip addr show | grep "inet " | grep -v "127.0.0.1"

echo ""
echo "2️⃣ Tailscale IP address:"
if command -v tailscale > /dev/null 2>&1; then
    tailscale ip 2>/dev/null || echo "   Tailscale IP not available"
else
    echo "   Tailscale not installed"
fi

echo ""
echo "3️⃣ WiFi IP address:"
ip addr show wlan0 2>/dev/null | grep "inet " || echo "   WiFi not available"

echo ""
echo "4️⃣ Ethernet IP address:"
ip addr show eth0 2>/dev/null | grep "inet " || echo "   Ethernet not available"

echo ""
echo "5️⃣ Default route:"
ip route | grep default | head -1

echo ""
echo "=============================="
echo "📊 IP ADDRESS SUMMARY"
echo "=============================="

echo "Current IP addresses that DGX Spark should use:"
ip addr show | grep "inet " | grep -v "127.0.0.1" | awk '{print "   " $2}' | cut -d'/' -f1

echo ""
echo "🎯 UPDATE CONSUMER URL:"
echo "If the IP address changed, update the consumer URL:"
echo "   Current consumer URL: udp://100.94.31.62:8554"
echo "   New URL should be: udp://<NEW_IP>:8554"

echo "=============================="
