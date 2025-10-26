#!/bin/bash

# Compare Local vs Docker Consumer Performance
# Tests if the issue is Docker-specific or general

echo "🔬 Local vs Docker Consumer Comparison"
echo "======================================"

PRODUCER_IP="100.94.31.62"
PRODUCER_PORT="8554"

echo "Testing with Producer: $PRODUCER_IP:$PRODUCER_PORT"
echo ""

# Test 1: Local Python consumer
echo "1️⃣ Testing LOCAL Python consumer..."
echo "   Running consumer locally for 10 seconds..."

timeout 10 python3 scripts/rtsp_consumer.py 2>&1 | head -20
LOCAL_EXIT_CODE=$?

echo ""
echo "   Local consumer exit code: $LOCAL_EXIT_CODE"

# Test 2: Docker consumer
echo ""
echo "2️⃣ Testing DOCKER consumer..."
echo "   Building Docker image..."

docker build -t rtsp-consumer-test . > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "   ❌ Docker build failed"
    exit 1
fi

echo "   ✅ Docker image built"

echo "   Running Docker consumer for 10 seconds..."
timeout 10 docker run --rm \
    --runtime=nvidia \
    --network=host \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GST_DEBUG=2 \
    -e PYTHONUNBUFFERED=1 \
    -e RTSP_URL=udp://$PRODUCER_IP:$PRODUCER_PORT \
    rtsp-consumer-test \
    /app/run_consumer.sh 2>&1 | head -20

DOCKER_EXIT_CODE=$?

echo ""
echo "   Docker consumer exit code: $DOCKER_EXIT_CODE"

# Test 3: Direct GStreamer test
echo ""
echo "3️⃣ Testing DIRECT GStreamer pipeline..."
echo "   Running GStreamer pipeline for 5 seconds..."

timeout 5 gst-launch-1.0 -v udpsrc port=$PRODUCER_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! fakesink 2>&1 | head -10
GST_EXIT_CODE=$?

echo ""
echo "   GStreamer exit code: $GST_EXIT_CODE"

# Summary
echo ""
echo "======================================"
echo "📊 COMPARISON SUMMARY"
echo "======================================"

if [ $LOCAL_EXIT_CODE -eq 124 ] || [ $LOCAL_EXIT_CODE -eq 0 ]; then
    echo "✅ Local Python consumer: WORKING"
else
    echo "❌ Local Python consumer: FAILED"
fi

if [ $DOCKER_EXIT_CODE -eq 124 ] || [ $DOCKER_EXIT_CODE -eq 0 ]; then
    echo "✅ Docker consumer: WORKING"
else
    echo "❌ Docker consumer: FAILED"
fi

if [ $GST_EXIT_CODE -eq 124 ] || [ $GST_EXIT_CODE -eq 0 ]; then
    echo "✅ Direct GStreamer: WORKING"
else
    echo "❌ Direct GStreamer: FAILED"
fi

echo ""
echo "🎯 ANALYSIS:"

if [ $LOCAL_EXIT_CODE -eq 124 ] && [ $DOCKER_EXIT_CODE -eq 124 ]; then
    echo "   Both local and Docker work - issue might be intermittent"
elif [ $LOCAL_EXIT_CODE -eq 124 ] && [ $DOCKER_EXIT_CODE -ne 124 ]; then
    echo "   Local works, Docker fails - DOCKER ISSUE"
elif [ $LOCAL_EXIT_CODE -ne 124 ] && [ $DOCKER_EXIT_CODE -eq 124 ]; then
    echo "   Docker works, local fails - LOCAL ENVIRONMENT ISSUE"
elif [ $LOCAL_EXIT_CODE -ne 124 ] && [ $DOCKER_EXIT_CODE -ne 124 ]; then
    echo "   Both fail - PRODUCER OR NETWORK ISSUE"
else
    echo "   Mixed results - need further investigation"
fi

if [ $GST_EXIT_CODE -eq 124 ] || [ $GST_EXIT_CODE -eq 0 ]; then
    echo "   GStreamer pipeline works - issue is in Python code"
else
    echo "   GStreamer pipeline fails - issue is with producer/network"
fi

echo "======================================"
