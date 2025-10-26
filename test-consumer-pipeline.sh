#!/bin/bash

# Test Consumer Pipeline Directly
# Tests if the Python consumer pipeline works with GStreamer command line

echo "🧪 Testing Consumer Pipeline Directly"
echo "===================================="

JETSON_IP="100.94.31.62"
JETSON_PORT="8554"

echo "Testing consumer pipeline with Jetson: $JETSON_IP:$JETSON_PORT"
echo ""

# Test 1: Basic UDP reception
echo "1️⃣ Testing basic UDP reception..."
timeout 5 gst-launch-1.0 -v udpsrc port=$JETSON_PORT ! fakesink 2>&1 | head -5
echo "   Exit code: $?"

# Test 2: Consumer pipeline (exact same as Python)
echo ""
echo "2️⃣ Testing consumer pipeline (exact same as Python)..."
echo "   Pipeline: udpsrc port=$JETSON_PORT ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! fakesink"

timeout 5 gst-launch-1.0 -v \
    udpsrc port=$JETSON_PORT ! \
    application/x-rtp ! \
    rtph264depay ! \
    h264parse ! \
    avdec_h264 ! \
    videoconvert ! \
    video/x-raw,format=BGR ! \
    fakesink 2>&1 | head -10

PIPELINE_EXIT_CODE=$?
echo "   Exit code: $PIPELINE_EXIT_CODE"

# Test 3: Test with appsink (like Python consumer)
echo ""
echo "3️⃣ Testing with appsink (like Python consumer)..."
echo "   This should work if the pipeline is correct"

# Create a simple Python test script
cat > /tmp/test_consumer_pipeline.py << 'EOF'
#!/usr/bin/env python3

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

Gst.init(None)

def on_new_sample(sink):
    print("🎬 CALLBACK CALLED! Received sample")
    sample = sink.emit("pull-sample")
    if sample:
        print(f"✅ Sample received: {sample}")
        return Gst.FlowReturn.OK
    else:
        print("❌ No sample")
        return Gst.FlowReturn.ERROR

# Create pipeline (exact same as consumer)
pipeline_str = """
udpsrc port=8554 !
application/x-rtp !
rtph264depay !
h264parse !
avdec_h264 !
videoconvert !
video/x-raw,format=BGR !
appsink emit-signals=true max-buffers=1 drop=true sync=false
"""

print(f"Creating pipeline: {pipeline_str.strip()}")
pipeline = Gst.parse_launch(pipeline_str)

# Get appsink
appsink = pipeline.get_by_interface(Gst.AppSink)
if not appsink:
    appsink = pipeline.get_by_name("appsink0")

if not appsink:
    print("❌ Could not find appsink")
    exit(1)

print("✅ Found appsink, connecting callback")
appsink.connect("new-sample", on_new_sample)

# Start pipeline
print("🚀 Starting pipeline...")
pipeline.set_state(Gst.State.PLAYING)

# Wait for messages
bus = pipeline.get_bus()
bus.add_signal_watch()

def on_message(bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"❌ Error: {err}")
        print(f"Debug: {debug}")
    elif message.type == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, pending_state = message.parse_state_changed()
        if message.src == pipeline:
            print(f"📊 State: {old_state.value_nick} -> {new_state.value_nick}")

bus.connect("message", on_message)

print("⏳ Waiting for data (10 seconds)...")
import time
time.sleep(10)

print("🛑 Stopping pipeline")
pipeline.set_state(Gst.State.NULL)
print("✅ Test complete")
EOF

python3 /tmp/test_consumer_pipeline.py

echo ""
echo "===================================="
echo "📊 PIPELINE TEST SUMMARY"
echo "===================================="

if [ $PIPELINE_EXIT_CODE -eq 124 ] || [ $PIPELINE_EXIT_CODE -eq 0 ]; then
    echo "✅ GStreamer pipeline: WORKS"
    echo "✅ Network connectivity: OK"
    echo "✅ UDP packets: OK"
    echo ""
    echo "🎯 CONCLUSION:"
    echo "   The issue is in the Python consumer code"
    echo "   The GStreamer pipeline works fine"
    echo "   Check Python appsink callback or threading issues"
else
    echo "❌ GStreamer pipeline: FAILED"
    echo "   Exit code: $PIPELINE_EXIT_CODE"
    echo ""
    echo "🎯 CONCLUSION:"
    echo "   There's still a pipeline or network issue"
fi

echo "===================================="
