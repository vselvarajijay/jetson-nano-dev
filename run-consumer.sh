#!/bin/bash
# Manual Docker Run Script for RTSP Consumer
# Use this if docker-compose has issues

echo "🚀 Building RTSP Consumer Docker image..."

# Build the image
docker build -t rtsp-consumer-dgx .

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo "🚀 Starting RTSP Consumer..."
    
    # Run the container manually
    docker run --rm \
        --runtime=nvidia \
        -e NVIDIA_VISIBLE_DEVICES=all \
        -e NVIDIA_DRIVER_CAPABILITIES=all \
        -e GST_DEBUG=2 \
        -e PYTHONUNBUFFERED=1 \
        -e RTSP_URL=udp://192.168.0.237:8554 \
        --name rtsp-consumer-manual \
        rtsp-consumer-dgx \
        python3 rtsp_consumer.py --url udp://192.168.0.237:8554
else
    echo "❌ Build failed!"
    exit 1
fi
