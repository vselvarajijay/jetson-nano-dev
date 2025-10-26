#!/bin/bash

# Simple UDP Listener Test
# Run this on DGX Spark to test if UDP packets are arriving

echo "📡 Simple UDP Listener Test"
echo "=========================="

echo "Listening for UDP packets on port 8554 for 10 seconds..."
echo "Press Ctrl+C to stop early"

# Start UDP listener
timeout 10 nc -u -l 8554

echo ""
echo "=========================="
echo "UDP listener test complete"
echo "=========================="
