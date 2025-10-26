#!/bin/bash

# Test Docker UDP Consumer Setup
# This script tests if the Docker container can receive UDP packets

echo "🧪 Testing Docker UDP Consumer Setup"
echo "==================================="

# Build the Docker image
echo "1️⃣ Building Docker image..."
docker build -t rtsp-consumer-dgx .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi
echo "✅ Docker image built successfully"

# Stop any existing container
echo "2️⃣ Cleaning up existing containers..."
docker stop rtsp-consumer-udp 2>/dev/null || true
docker rm rtsp-consumer-udp 2>/dev/null || true

# Test with host networking
echo "3️⃣ Testing with host networking..."
echo "Starting consumer container with host networking..."

# Run container with host networking
docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL=udp://100.94.31.62:8554 \
    --name rtsp-consumer-udp \
    rtsp-consumer-dgx \
    /app/run_consumer.sh &

CONTAINER_PID=$!

# Wait a bit for container to start
echo "4️⃣ Waiting for container to start..."
sleep 5

# Check if container is running
if docker ps | grep -q rtsp-consumer-udp; then
    echo "✅ Container is running"
    
    # Wait for some output
    echo "5️⃣ Waiting for consumer output (10 seconds)..."
    sleep 10
    
    # Check container logs
    echo "6️⃣ Checking container logs..."
    docker logs rtsp-consumer-udp --tail 20
    
    # Stop the container
    echo "7️⃣ Stopping container..."
    docker stop rtsp-consumer-udp
else
    echo "❌ Container failed to start"
    docker logs rtsp-consumer-udp 2>/dev/null || echo "No logs available"
fi

echo "==================================="
echo "Docker UDP test complete"
echo "==================================="
