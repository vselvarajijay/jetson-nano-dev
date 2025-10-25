#!/bin/bash

# Docker Consumer Runner Script
# This script runs the RTSP consumer inside a Docker container

echo "🐳 Starting RTSP Consumer in Docker..."
echo "======================================="

# Default URL
RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}

echo "🔗 Using stream URL: $RTSP_URL"
echo ""

# Build the Docker image if it doesn't exist
echo "🔨 Building Docker image..."
docker build -t rtsp-consumer-dgx .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi

echo "✅ Docker build successful"
echo ""

# Run the consumer in Docker
echo "🚀 Starting consumer in Docker container..."
echo "============================================"

docker run --rm \
    --runtime=nvidia \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL="$RTSP_URL" \
    --name rtsp-consumer-docker \
    rtsp-consumer-dgx

echo ""
echo "🏁 Consumer finished"
