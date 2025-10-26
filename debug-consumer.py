#!/usr/bin/env python3

# Debug Consumer - Simplified version to isolate the issue
# This tests the exact same pipeline as the main consumer

import gi
import sys
import os
import time

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GLib, GstApp

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

def on_bus_message(bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"❌ GStreamer Error: {err}")
        print(f"Debug info: {debug}")
    elif message.type == Gst.MessageType.WARNING:
        warn, debug = message.parse_warning()
        print(f"⚠️  GStreamer Warning: {warn}")
        print(f"Debug info: {debug}")
    elif message.type == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, pending_state = message.parse_state_changed()
        if message.src == pipeline:
            print(f"📊 Pipeline state: {old_state.value_nick} -> {new_state.value_nick}")
    elif message.type == Gst.MessageType.STREAM_START:
        print("🎥 Stream started")
    elif message.type == Gst.MessageType.EOS:
        print("🏁 End of stream")

# Get URL from environment
rtsp_url = os.getenv('RTSP_URL', 'udp://100.94.31.62:8554')
print(f"🔗 Using URL: {rtsp_url}")

# Parse URL
if rtsp_url.startswith('udp://'):
    url_parts = rtsp_url[6:]  # Remove 'udp://'
    if ':' in url_parts:
        host, port = url_parts.split(':', 1)
    else:
        host = url_parts
        port = "8554"
else:
    host = "127.0.0.1"
    port = "8554"

print(f"🔗 Parsed: host={host}, port={port}")

# Create pipeline (exact same as main consumer)
pipeline_str = f"""
udpsrc port={port} !
application/x-rtp !
rtph264depay !
h264parse !
avdec_h264 !
videoconvert !
video/x-raw,format=BGR !
appsink emit-signals=true max-buffers=1 drop=true sync=false
"""

print(f"🔗 Pipeline: {pipeline_str.strip()}")
pipeline = Gst.parse_launch(pipeline_str)

# Add bus message handler
bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message", on_bus_message)

# Get appsink
appsink = pipeline.get_by_interface(Gst.AppSink)
if not appsink:
    appsink = pipeline.get_by_name("appsink0")

if not appsink:
    print("❌ Could not find appsink")
    sys.exit(1)

print("✅ Found appsink, connecting callback")
appsink.connect("new-sample", on_new_sample)

# Start pipeline
print("🚀 Starting pipeline...")
ret = pipeline.set_state(Gst.State.PLAYING)
print(f"📊 Pipeline state change result: {ret}")

# Wait for pipeline to start
time.sleep(2)

# Check pipeline state
state = pipeline.get_state(timeout=2 * Gst.SECOND)
print(f"📊 Pipeline state: {state}")

if state[0] == Gst.StateChangeReturn.FAILURE:
    print("❌ Pipeline failed to start!")
    sys.exit(1)

print("✅ Pipeline started successfully")
print("⏳ Waiting for frames (15 seconds)...")

# Wait for frames
time.sleep(15)

print("🛑 Stopping pipeline")
pipeline.set_state(Gst.State.NULL)
print("✅ Debug test complete")
