#!/bin/bash

# Safe Consumer Runner Script
# This script safely starts the RTSP consumer by:
# 1. Killing any existing consumer processes
# 2. Ensuring clean environment
# 3. Starting the consumer with proper error handling

echo "🎥 Starting RTSP Consumer..."
echo "============================="

# Function to kill existing consumer processes
kill_existing_consumers() {
    echo "🔍 Checking for existing consumer processes..."
    
    # Find Python processes running the consumer
    CONSUMER_PIDS=$(ps aux | grep -E "python.*rtsp_consumer" | grep -v grep | awk '{print $2}')
    
    if [ -n "$CONSUMER_PIDS" ]; then
        echo "⚠️  Found existing consumer processes: $CONSUMER_PIDS"
        echo "🛑 Killing existing processes..."
        
        for pid in $CONSUMER_PIDS; do
            echo "   Killing PID: $pid"
            kill $pid 2>/dev/null
        done
        
        # Wait a moment for processes to terminate
        sleep 2
        
        # Force kill if still running
        for pid in $CONSUMER_PIDS; do
            if kill -0 $pid 2>/dev/null; then
                echo "   Force killing PID: $pid"
                kill -9 $pid 2>/dev/null
            fi
        done
        
        sleep 1
        echo "✅ Existing processes terminated"
    else
        echo "✅ No existing consumer processes found"
    fi
}

# Function to kill Docker containers
kill_docker_containers() {
    echo "🔍 Checking for Docker consumer containers..."
    
    # Find Docker containers running the consumer
    CONTAINER_IDS=$(docker ps -q --filter "name=rtsp-consumer")
    
    if [ -n "$CONTAINER_IDS" ]; then
        echo "⚠️  Found Docker consumer containers: $CONTAINER_IDS"
        echo "🛑 Stopping Docker containers..."
        
        for container_id in $CONTAINER_IDS; do
            echo "   Stopping container: $container_id"
            docker stop $container_id 2>/dev/null
        done
        
        sleep 2
        echo "✅ Docker containers stopped"
    else
        echo "✅ No Docker consumer containers found"
    fi
}

# Function to check environment
check_environment() {
    echo "🔍 Checking environment..."
    
    # Check if we're in the right directory
    if [ ! -f "scripts/rtsp_consumer.py" ]; then
        echo "❌ Error: scripts/rtsp_consumer.py not found!"
        echo "Please run this script from the project root directory"
        exit 1
    fi
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        echo "❌ Error: docker not found!"
        echo "Please install Docker"
        exit 1
    fi
    
    # Check if nvidia-docker is available
    if ! docker info | grep -q nvidia; then
        echo "⚠️  Warning: nvidia runtime not detected"
        echo "Container will start without GPU access"
    fi
    
    echo "✅ Environment checks passed"
}

# Function to test network connectivity
test_connectivity() {
    echo "🔍 Testing network connectivity..."
    
    # Get RTSP_URL from environment or use default
    RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}
    
    echo "   Testing URL: $RTSP_URL"
    
    # Parse URL for ping test
    if [[ $RTSP_URL =~ ^udp://([^:]+):([0-9]+)$ ]]; then
        HOST=${BASH_REMATCH[1]}
        PORT=${BASH_REMATCH[2]}
        
        echo "   Host: $HOST, Port: $PORT"
        
        # Test ping
        if ping -c 2 $HOST >/dev/null 2>&1; then
            echo "   ✅ Ping to $HOST successful"
        else
            echo "   ⚠️  Ping to $HOST failed (may still work for UDP)"
        fi
        
        # Test UDP port
        if timeout 3 nc -u -z $HOST $PORT 2>/dev/null; then
            echo "   ✅ UDP port $PORT accessible"
        else
            echo "   ⚠️  UDP port $PORT not accessible (producer may not be running)"
        fi
    else
        echo "   ⚠️  Could not parse URL: $RTSP_URL"
    fi
    
    echo "✅ Connectivity test completed"
}

# Function to start consumer with error handling
start_consumer() {
    echo "🎥 Starting RTSP Consumer in Docker..."
    echo "========================================"
    
    # Set up signal handler for graceful shutdown
    trap 'echo -e "\n🛑 Received interrupt signal. Shutting down..."; exit 0' INT TERM
    
    # Get RTSP_URL from environment or use default
    RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}
    
    echo "🔗 Using stream URL: $RTSP_URL"
    echo "=================================="
    
    # Build Docker image if needed
    echo "🔨 Building Docker image..."
    docker build -t rtsp-consumer-dgx -f Dockerfile .
    
    if [ $? -ne 0 ]; then
        echo "❌ Docker build failed!"
        exit 1
    fi
    
    echo "✅ Docker image built successfully"
    echo ""
    
    # Run the consumer in Docker
    echo "🚀 Starting consumer container..."
    
    docker run --rm \
        --runtime=nvidia \
        --network=host \
        -e NVIDIA_VISIBLE_DEVICES=all \
        -e NVIDIA_DRIVER_CAPABILITIES=all \
        -e GST_DEBUG=2 \
        -e PYTHONUNBUFFERED=1 \
        -e RTSP_URL="$RTSP_URL" \
        --name rtsp-consumer-dgx \
        rtsp-consumer-dgx
    
    # Check exit status
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Consumer exited normally"
    else
        echo "❌ Consumer exited with error code: $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -u, --url URL  Set RTSP_URL environment variable"
    echo ""
    echo "Environment variables:"
    echo "  RTSP_URL       Stream URL (default: udp://100.94.31.62:8554)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use default URL"
    echo "  $0 -u udp://192.168.0.237:8554       # Use WiFi IP"
    echo "  RTSP_URL=udp://100.94.31.62:8554 $0  # Use environment variable"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -u|--url)
            export RTSP_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "🎬 RTSP Consumer Safe Runner"
    echo "============================"
    
    # Run safety checks
    kill_existing_consumers
    kill_docker_containers
    check_environment
    test_connectivity
    
    echo ""
    echo "🚀 All checks passed! Starting consumer..."
    echo "=========================================="
    
    # Start the consumer
    start_consumer
}

# Run main function
main "$@"