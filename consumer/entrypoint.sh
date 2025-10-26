#!/bin/bash
# RTSP Consumer Docker Entrypoint Script
# Handles container initialization and environment setup

set -e

echo "🚀 Starting RTSP Consumer Container..."

# Function to check if GStreamer is working
check_gstreamer() {
    echo "🔍 Checking GStreamer installation..."
    python3 -c "
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)
print('✅ GStreamer is working correctly')
"
}

# Function to check CUDA availability
check_cuda() {
    echo "🔍 Checking CUDA availability..."
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits
        echo "✅ NVIDIA GPU detected"
    else
        echo "⚠️  NVIDIA GPU not detected (running in CPU mode)"
    fi
}

# Function to validate stream URL (RTSP or UDP)
validate_stream_url() {
    local url=$1
    if [[ $url =~ ^rtsp:// ]] || [[ $url =~ ^udp:// ]]; then
        echo "✅ Stream URL format is valid: $url"
    else
        echo "❌ Invalid stream URL format: $url"
        echo "Expected format: rtsp://host:port/path or udp://host:port"
        exit 1
    fi
}

# Function to test network connectivity
test_connectivity() {
    local url=$1
    local host=$(echo $url | sed -n 's/rtsp:\/\/\([^:]*\):.*/\1/p')
    local port=$(echo $url | sed -n 's/rtsp:\/\/[^:]*:\([^/]*\)\/.*/\1/p')
    
    if [ -n "$host" ] && [ -n "$port" ]; then
        echo "🔍 Testing connectivity to $host:$port..."
        if timeout 5 bash -c "</dev/tcp/$host/$port"; then
            echo "✅ Network connectivity to $host:$port is working"
        else
            echo "⚠️  Cannot connect to $host:$port (will retry during runtime)"
        fi
    fi
}

# Main initialization
main() {
    echo "=" * 60
    echo "🎥 RTSP Consumer Container Initialization"
    echo "=" * 60
    
    # Check system dependencies
    check_gstreamer
    check_cuda
    
    # Validate RTSP_URL environment variable if set
    if [ -n "$RTSP_URL" ]; then
        validate_stream_url "$RTSP_URL"
        # Only test connectivity for RTSP URLs (not UDP)
        if [[ $RTSP_URL =~ ^rtsp:// ]]; then
            test_connectivity "$RTSP_URL"
        fi
    fi
    
    # Create necessary directories
    mkdir -p /app/output /app/logs
    
    # Set up environment variables
    export GST_DEBUG=${GST_DEBUG:-2}
    export GST_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gstreamer-1.0
    
    echo "=" * 60
    echo "✅ Container initialization complete"
    echo "=" * 60
    
    # If RTSP_URL is provided, run the consumer script
    if [ -n "$RTSP_URL" ]; then
        echo "🚀 Starting RTSP Consumer with URL: $RTSP_URL"
        exec python3 /app/rtsp_consumer.py
    else
        # Otherwise execute the provided command
        exec "$@"
    fi
}

# Run main function with all arguments
main "$@"
