#!/bin/bash

# Debug Consumer in Docker
# Tests the consumer pipeline inside Docker container

echo "🐳 Debug Consumer in Docker"
echo "=========================="

JETSON_IP="100.94.31.62"
JETSON_PORT="8554"

echo "Testing consumer pipeline in Docker with Jetson: $JETSON_IP:$JETSON_PORT"
echo ""

# Build the Docker image
echo "1️⃣ Building Docker image..."
docker build -t rtsp-consumer-debug .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi
echo "✅ Docker image built successfully"

# Stop any existing container
echo "2️⃣ Cleaning up existing containers..."
docker stop rtsp-consumer-debug 2>/dev/null || true
docker rm rtsp-consumer-debug 2>/dev/null || true

# Test 1: Debug consumer in Docker
echo ""
echo "3️⃣ Testing debug consumer in Docker..."
echo "   Running simplified consumer for 15 seconds..."

docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL=udp://$JETSON_IP:$JETSON_PORT \
    --name rtsp-consumer-debug \
    rtsp-consumer-debug \
    python3 debug-consumer.py

DEBUG_EXIT_CODE=$?
echo "   Debug consumer exit code: $DEBUG_EXIT_CODE"

# Test 2: Test consumer pipeline in Docker
echo ""
echo "4️⃣ Testing consumer pipeline in Docker..."
echo "   Running pipeline test for 10 seconds..."

docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL=udp://$JETSON_IP:$JETSON_PORT \
    --name rtsp-consumer-pipeline-test \
    rtsp-consumer-debug \
    bash -c "timeout 10 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! fakesink"

PIPELINE_EXIT_CODE=$?
echo "   Pipeline test exit code: $PIPELINE_EXIT_CODE"

# Test 3: Test basic UDP reception in Docker
echo ""
echo "5️⃣ Testing basic UDP reception in Docker..."
echo "   Running UDP test for 5 seconds..."

docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    --name rtsp-consumer-udp-test \
    rtsp-consumer-debug \
    bash -c "timeout 5 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! fakesink"

UDP_EXIT_CODE=$?
echo "   UDP test exit code: $UDP_EXIT_CODE"

# Summary
echo ""
echo "=========================="
echo "📊 DOCKER DEBUG SUMMARY"
echo "=========================="

if [ $UDP_EXIT_CODE -eq 124 ] || [ $UDP_EXIT_CODE -eq 0 ]; then
    echo "✅ UDP reception in Docker: OK"
else
    echo "❌ UDP reception in Docker: FAILED"
fi

if [ $PIPELINE_EXIT_CODE -eq 124 ] || [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    echo "✅ Pipeline in Docker: OK"
else
    echo "❌ Pipeline in Docker: FAILED"
fi

if [ $DEBUG_EXIT_CODE -eq 0 ]; then
    echo "✅ Debug consumer in Docker: OK"
else
    echo "❌ Debug consumer in Docker: FAILED"
fi

echo ""
echo "🎯 ANALYSIS:"

if [ $UDP_EXIT_CODE -eq 124 ] && [ $PIPELINE_EXIT_CODE -eq 124 ] && [ $DEBUG_EXIT_CODE -eq 0 ]; then
    echo "✅ Everything works in Docker"
    echo "   - UDP reception: OK"
    echo "   - Pipeline: OK"
    echo "   - Debug consumer: OK"
    echo "   - Issue is in main consumer logic"
elif [ $UDP_EXIT_CODE -eq 124 ] && [ $PIPELINE_EXIT_CODE -ne 124 ]; then
    echo "❌ Pipeline issue in Docker"
    echo "   - UDP reception: OK"
    echo "   - Pipeline: FAILED"
    echo "   - Issue is in GStreamer pipeline"
elif [ $UDP_EXIT_CODE -ne 124 ]; then
    echo "❌ UDP reception issue in Docker"
    echo "   - UDP reception: FAILED"
    echo "   - Network or Docker networking issue"
else
    echo "❌ Mixed results - need further investigation"
fi

echo "=========================="
