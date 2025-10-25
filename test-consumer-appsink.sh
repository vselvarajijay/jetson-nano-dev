#!/bin/bash

# Simple Consumer Test
# Tests if the consumer can receive and process frames

echo "🧪 Simple Consumer Test"
echo "======================="

RTSP_URL=${RTSP_URL:-"udp://100.94.31.62:8554"}

echo "🔗 Testing URL: $RTSP_URL"
echo ""

# Test 1: Check if producer is sending data
echo "1️⃣ Checking if producer is sending data..."
timeout 3 gst-launch-1.0 udpsrc port=8554 ! fakesink

if [ $? -eq 124 ]; then
    echo "   ✅ Producer is sending UDP packets"
else
    echo "   ❌ Producer is NOT sending UDP packets"
    echo "   Check if producer is running on Jetson Nano"
    exit 1
fi

echo ""

# Test 2: Test consumer pipeline with appsink
echo "2️⃣ Testing consumer pipeline with appsink..."
echo "   This should show if appsink receives data"

# Create a simple test script
cat > /tmp/test_appsink.py << 'EOF'
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

# Create pipeline
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

python3 /tmp/test_appsink.py

echo ""
echo "💡 If you see '🎬 CALLBACK CALLED!' above, the appsink is working"
echo "   If you don't see it, there's an issue with the pipeline or network"
