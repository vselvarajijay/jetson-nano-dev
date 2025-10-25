#!/bin/bash

# Test Docker Container GStreamer Installation
# This script tests if the Docker container has GStreamer properly installed

echo "🧪 Testing Docker Container GStreamer Installation"
echo "=================================================="

# Test 1: Build the Docker image
echo "1️⃣ Building Docker image..."
docker build -t rtsp-consumer-test .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi

echo "✅ Docker build successful"

# Test 2: Test GStreamer import in container
echo "2️⃣ Testing GStreamer import in container..."
docker run --rm rtsp-consumer-test python3 -c "
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)
print('✅ GStreamer import successful')
print(f'GStreamer version: {Gst.version_string()}')
"

if [ $? -ne 0 ]; then
    echo "❌ GStreamer import failed in container!"
    exit 1
fi

# Test 3: Test the consumer script
echo "3️⃣ Testing consumer script in container..."
docker run --rm \
    -e RTSP_URL="udp://100.94.31.62:8554" \
    rtsp-consumer-test \
    timeout 5 python3 rtsp_consumer.py

if [ $? -eq 124 ]; then
    echo "✅ Consumer script runs successfully (timeout expected)"
elif [ $? -eq 0 ]; then
    echo "✅ Consumer script completed successfully"
else
    echo "❌ Consumer script failed!"
    exit 1
fi

echo ""
echo "🎉 All tests passed! Docker container is ready."
echo ""
echo "To run the consumer:"
echo "  docker run --rm -e RTSP_URL=udp://100.94.31.62:8554 rtsp-consumer-test"
echo ""
echo "Or use docker-compose:"
echo "  docker-compose up"
