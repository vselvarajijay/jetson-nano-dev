import gi
import cv2
import numpy as np
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib, GstApp

# Initialize GStreamer
Gst.init(None)

# Define callback BEFORE linking it to the pipeline
def on_new_sample(sink):
    sample = sink.emit("pull-sample")
    buf = sample.get_buffer()
    caps = sample.get_caps()
    width = caps.get_structure(0).get_value("width")
    height = caps.get_structure(0).get_value("height")

    success, map_info = buf.map(Gst.MapFlags.READ)
    if not success:
        return Gst.FlowReturn.ERROR

    # Convert to numpy array
    frame = np.ndarray(
        (height, width, 3),
        buffer=map_info.data,
        dtype=np.uint8,
    )
    buf.unmap(map_info)

    # 🧠 Your Python processing here (grayscale + stats)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_intensity = float(np.mean(gray))
    print(f"🧠 Frame processed: mean intensity={mean_intensity:.2f}")

    return Gst.FlowReturn.OK


# 🔧 Define your GStreamer pipeline
pipeline_str = """
v4l2src device=/dev/video4 io-mode=2 !
video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 !
videoconvert !
video/x-raw,format=BGR !
appsink emit-signals=true max-buffers=1 drop=true sync=false
"""

print("🎥 Running RealSense (/dev/video4) → Python frame processing...")

# Parse and set up pipeline
pipeline = Gst.parse_launch(pipeline_str)

# Get appsink element
appsink = pipeline.get_by_interface(GstApp.AppSink)
if not appsink:
    appsink = pipeline.get_by_name("appsink0")
appsink.connect("new-sample", on_new_sample)

# Start pipeline
pipeline.set_state(Gst.State.PLAYING)

try:
    loop = GLib.MainLoop()
    loop.run()
except KeyboardInterrupt:
    print("\n🛑 Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)