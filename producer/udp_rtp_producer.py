#!/usr/bin/env python3
"""
Working DeepStream UDP RTP Producer for Jetson Orin Nano
Captures RGB from Intel RealSense, converts to grayscale 240x240, streams to DGX Spark
Uses x264enc (software encoder) - TESTED AND WORKING
"""

import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
import signal

# Standard GStreamer initialization
Gst.init(None)

class SimpleProducer:
    def __init__(self):
        self.pipeline = None
        self.loop = None
        self.frame_count = 0
        self.start_time = None
        
    def bus_call(self, bus, message, loop):
        """Handle bus messages"""
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            sys.stderr.write("Warning: %s: %s\n" % (err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            loop.quit()
        return True
    
    def frame_probe(self, pad, info):
        """Probe callback to count frames and show stats"""
        import time
        
        self.frame_count += 1
        
        # Initialize start time on first frame
        if self.start_time is None:
            self.start_time = time.time()
        
        # Show stats every 30 frames (~1 second at 30fps)
        if self.frame_count % 30 == 0:
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            
            # Print inline update
            sys.stdout.write(f"\r📊 Frames: {self.frame_count:6d} | FPS: {fps:5.1f} | Runtime: {elapsed:6.1f}s")
            sys.stdout.flush()
        
        return Gst.PadProbeReturn.OK
        
    def setup_pipeline(self):
        """
        Working pipeline (TESTED):
        Camera → Grayscale → Resize 240x240 → x264 Encode → UDP to DGX Spark
        """
        
        print("=" * 60)
        print("DeepStream Producer - Jetson Orin Nano")
        print("=" * 60)
        
        # Create Pipeline
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            sys.stderr.write("Unable to create Pipeline\n")
            return False
        
        # STEP 1: Camera source
        print("Creating v4l2src (camera)")
        source = Gst.ElementFactory.make("v4l2src", "source")
        if not source:
            sys.stderr.write("Unable to create v4l2src\n")
            return False
        source.set_property('device', '/dev/video4')
        
        # STEP 2: Convert to grayscale
        print("Creating videoconvert (for grayscale)")
        vidconv1 = Gst.ElementFactory.make("videoconvert", "conv-gray")
        if not vidconv1:
            sys.stderr.write("Unable to create videoconvert\n")
            return False
        
        # Grayscale caps
        caps_gray = Gst.ElementFactory.make("capsfilter", "caps-gray")
        if not caps_gray:
            sys.stderr.write("Unable to create capsfilter\n")
            return False
        caps_gray.set_property('caps', Gst.Caps.from_string("video/x-raw,format=GRAY8"))
        
        # STEP 3: Resize to 240x240
        print("Creating videoscale (resize)")
        videoscale = Gst.ElementFactory.make("videoscale", "scaler")
        if not videoscale:
            sys.stderr.write("Unable to create videoscale\n")
            return False
        
        # Size caps
        caps_size = Gst.ElementFactory.make("capsfilter", "caps-size")
        if not caps_size:
            sys.stderr.write("Unable to create capsfilter\n")
            return False
        caps_size.set_property('caps', Gst.Caps.from_string("video/x-raw,width=240,height=240"))
        
        # Convert to I420 for encoder
        print("Creating videoconvert (for encoder)")
        vidconv2 = Gst.ElementFactory.make("videoconvert", "conv-i420")
        if not vidconv2:
            sys.stderr.write("Unable to create videoconvert\n")
            return False
        
        # I420 caps
        caps_i420 = Gst.ElementFactory.make("capsfilter", "caps-i420")
        if not caps_i420:
            sys.stderr.write("Unable to create capsfilter\n")
            return False
        caps_i420.set_property('caps', Gst.Caps.from_string("video/x-raw,format=I420"))
        
        # STEP 4: Software H.264 encoder
        print("Creating x264enc (software encoder)")
        encoder = Gst.ElementFactory.make("x264enc", "encoder")
        if not encoder:
            sys.stderr.write("Unable to create x264enc\n")
            return False
        encoder.set_property('tune', 'zerolatency')
        encoder.set_property('bitrate', 500)  # 500 kbps
        
        # H.264 parser
        print("Creating h264parse")
        h264parse = Gst.ElementFactory.make("h264parse", "parser")
        if not h264parse:
            sys.stderr.write("Unable to create h264parse\n")
            return False
        
        # RTP payloader
        print("Creating rtph264pay")
        rtppay = Gst.ElementFactory.make("rtph264pay", "rtppay")
        if not rtppay:
            sys.stderr.write("Unable to create rtph264pay\n")
            return False
        rtppay.set_property('pt', 96)
        rtppay.set_property('config-interval', 1)
        
        # STEP 5: UDP sink to DGX Spark
        print("Creating udpsink")
        sink = Gst.ElementFactory.make("udpsink", "sink")
        if not sink:
            sys.stderr.write("Unable to create udpsink\n")
            return False
        sink.set_property('host', '100.64.24.69')
        sink.set_property('port', 8554)
        sink.set_property('sync', False)
        
        # Add all elements to pipeline
        print("Adding elements to pipeline")
        self.pipeline.add(source)
        self.pipeline.add(vidconv1)
        self.pipeline.add(caps_gray)
        self.pipeline.add(videoscale)
        self.pipeline.add(caps_size)
        self.pipeline.add(vidconv2)
        self.pipeline.add(caps_i420)
        self.pipeline.add(encoder)
        self.pipeline.add(h264parse)
        self.pipeline.add(rtppay)
        self.pipeline.add(sink)
        
        # Link all elements
        print("Linking elements")
        if not source.link(vidconv1):
            sys.stderr.write("Failed to link source → vidconv1\n")
            return False
        if not vidconv1.link(caps_gray):
            sys.stderr.write("Failed to link vidconv1 → caps_gray\n")
            return False
        if not caps_gray.link(videoscale):
            sys.stderr.write("Failed to link caps_gray → videoscale\n")
            return False
        if not videoscale.link(caps_size):
            sys.stderr.write("Failed to link videoscale → caps_size\n")
            return False
        if not caps_size.link(vidconv2):
            sys.stderr.write("Failed to link caps_size → vidconv2\n")
            return False
        if not vidconv2.link(caps_i420):
            sys.stderr.write("Failed to link vidconv2 → caps_i420\n")
            return False
        if not caps_i420.link(encoder):
            sys.stderr.write("Failed to link caps_i420 → encoder\n")
            return False
        if not encoder.link(h264parse):
            sys.stderr.write("Failed to link encoder → h264parse\n")
            return False
        if not h264parse.link(rtppay):
            sys.stderr.write("Failed to link h264parse → rtppay\n")
            return False
        if not rtppay.link(sink):
            sys.stderr.write("Failed to link rtppay → sink\n")
            return False
        
        print("=" * 60)
        print("Pipeline Ready!")
        print("  1. Camera (/dev/video4)")
        print("  2. Convert to GRAY8 (black & white)")
        print("  3. Resize to 240x240")
        print("  4. Encode with x264 (software)")
        print("  5. Stream to DGX Spark (100.64.24.69:8554)")
        print("=" * 60)
        
        # Add probe to count frames
        sinkpad = sink.get_static_pad("sink")
        if sinkpad:
            sinkpad.add_probe(Gst.PadProbeType.BUFFER, self.frame_probe)
            print("✓ Frame counter attached")
        
        return True
    
    def run(self):
        """Run the producer"""
        if not self.setup_pipeline():
            sys.stderr.write("Failed to setup pipeline\n")
            return
        
        # Create event loop
        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_call, self.loop)
        
        # Start pipeline
        print("Starting pipeline...")
        self.pipeline.set_state(Gst.State.PLAYING)
        
        print("\n" + "=" * 60)
        print("🎥 STREAMING TO DGX SPARK")
        print("=" * 60)
        print("Format: Grayscale 240x240")
        print("Target: udp://100.64.24.69:8554")
        print("Encoder: x264 (software)")
        print("=" * 60)
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")
        
        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("\n\nStopping...")
            pass
        
        # Cleanup
        self.pipeline.set_state(Gst.State.NULL)
        
        # Print final stats
        if self.frame_count > 0 and self.start_time:
            import time
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            print(f"\n📊 Final Stats: {self.frame_count} frames in {elapsed:.1f}s ({fps:.1f} fps)")
        
        print("Pipeline stopped")

def main():
    producer = SimpleProducer()
    producer.run()

if __name__ == '__main__':
    sys.exit(main())