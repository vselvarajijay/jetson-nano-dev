#!/bin/bash

# Simple Docker run command for RTSP Consumer
# Bypasses Docker Compose to avoid volume configuration issues

echo "🚀 Running RTSP Consumer with Docker"
echo "============================================="

# Build the image
echo "1️⃣ Building Docker image..."
docker build -t rtsp-consumer-dgx .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi
echo "✅ Docker image built successfully"

# Stop any existing container
echo "2️⃣ Cleaning up existing containers..."
docker stop rtsp-consumer-simple 2>/dev/null || true
docker rm rtsp-consumer-simple 2>/dev/null || true

# Run the container
echo "3️⃣ Running consumer container..."
docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL=udp://100.94.31.62:8554 \
    --name rtsp-consumer-simple \
    rtsp-consumer-dgx \
    /app/run_consumer.sh

echo "============================================="
echo "Docker run complete"
echo "============================================="
