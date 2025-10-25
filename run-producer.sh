#!/bin/bash

# Safe Producer Runner Script
# This script safely starts the UDP RTP producer by:
# 1. Killing any existing producer processes
# 2. Ensuring the camera is free
# 3. Starting the producer with proper error handling

echo "🚀 Starting UDP RTP Producer..."
echo "=================================="

# Function to kill existing producer processes
kill_existing_producers() {
    echo "🔍 Checking for existing producer processes..."
    
    # Find Python processes running the producer
    PRODUCER_PIDS=$(ps aux | grep -E "python.*udp_rtp_producer" | grep -v grep | awk '{print $2}')
    
    if [ -n "$PRODUCER_PIDS" ]; then
        echo "⚠️  Found existing producer processes: $PRODUCER_PIDS"
        echo "🛑 Killing existing processes..."
        
        for pid in $PRODUCER_PIDS; do
            echo "   Killing PID: $pid"
            kill $pid 2>/dev/null
        done
        
        # Wait a moment for processes to terminate
        sleep 2
        
        # Force kill if still running
        for pid in $PRODUCER_PIDS; do
            if kill -0 $pid 2>/dev/null; then
                echo "   Force killing PID: $pid"
                kill -9 $pid 2>/dev/null
            fi
        done
        
        sleep 1
        echo "✅ Existing processes terminated"
    else
        echo "✅ No existing producer processes found"
    fi
}

# Function to check camera availability
check_camera() {
    echo "🔍 Checking camera availability..."
    
    if [ ! -e "/dev/video4" ]; then
        echo "❌ Camera device /dev/video4 not found!"
        echo "Available video devices:"
        ls -la /dev/video* 2>/dev/null || echo "No video devices found"
        exit 1
    fi
    
    # Check if camera is busy
    CAMERA_USERS=$(lsof /dev/video4 2>/dev/null | grep -v COMMAND | wc -l)
    if [ "$CAMERA_USERS" -gt 0 ]; then
        echo "⚠️  Camera /dev/video4 is busy. Users:"
        lsof /dev/video4 2>/dev/null | grep -v COMMAND
        echo "🛑 Attempting to free camera..."
        
        # Kill processes using the camera
        CAMERA_PIDS=$(lsof /dev/video4 2>/dev/null | grep -v COMMAND | awk '{print $2}' | sort -u)
        for pid in $CAMERA_PIDS; do
            echo "   Killing camera user PID: $pid"
            kill $pid 2>/dev/null
        done
        
        sleep 2
        
        # Check again
        CAMERA_USERS=$(lsof /dev/video4 2>/dev/null | grep -v COMMAND | wc -l)
        if [ "$CAMERA_USERS" -gt 0 ]; then
            echo "❌ Camera still busy after cleanup attempt"
            echo "You may need to manually kill processes or restart the system"
            exit 1
        fi
    fi
    
    echo "✅ Camera /dev/video4 is available"
}

# Function to test basic GStreamer pipeline
test_pipeline() {
    echo "🔍 Testing basic GStreamer pipeline..."
    
    timeout 3 gst-launch-1.0 v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! fakesink >/dev/null 2>&1
    
    if [ $? -eq 124 ]; then
        echo "✅ Basic pipeline test successful (timeout expected)"
    elif [ $? -eq 0 ]; then
        echo "✅ Basic pipeline test successful"
    else
        echo "❌ Basic pipeline test failed"
        echo "Camera may not be working properly"
        exit 1
    fi
}

# Function to start producer with error handling
start_producer() {
    echo "🎥 Starting UDP RTP Producer..."
    echo "=================================="
    
    # Set up signal handler for graceful shutdown
    trap 'echo -e "\n🛑 Received interrupt signal. Shutting down..."; exit 0' INT TERM
    
    # Start the producer
    python3 scripts/udp_rtp_producer.py
    
    # Check exit status
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Producer exited normally"
    else
        echo "❌ Producer exited with error code: $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

# Main execution
main() {
    echo "🎬 UDP RTP Producer Safe Runner"
    echo "================================"
    
    # Check if we're in the right directory
    if [ ! -f "scripts/udp_rtp_producer.py" ]; then
        echo "❌ Error: scripts/udp_rtp_producer.py not found!"
        echo "Please run this script from the project root directory"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo "❌ Error: python3 not found!"
        exit 1
    fi
    
    # Check if GStreamer is available
    if ! command -v gst-launch-1.0 &> /dev/null; then
        echo "❌ Error: gst-launch-1.0 not found!"
        echo "Please install GStreamer development packages"
        exit 1
    fi
    
    # Run safety checks
    kill_existing_producers
    check_camera
    test_pipeline
    
    echo ""
    echo "🚀 All checks passed! Starting producer..."
    echo "=========================================="
    
    # Start the producer
    start_producer
}

# Run main function
main "$@"
