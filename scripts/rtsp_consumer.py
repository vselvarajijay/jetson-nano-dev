#!/usr/bin/env python3
"""
RTSP Consumer
Connects to RTSP stream and processes frames with DeepStream, printing frame statistics
"""

import gi
import cv2
import numpy as np
import threading
import time
import logging
import argparse

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib, GstApp

# Initialize GStreamer
Gst.init(None)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RTSPConsumer:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.frame = None
        self.lock = threading.Lock()
        self.pipeline = None
        self.running = False
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_time = time.time()
        self.last_fps_count = 0
        
    def on_new_sample(self, sink):
        """Callback function for new video samples from GStreamer"""
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR
            
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

        # Store frame for processing
        with self.lock:
            self.frame = frame.copy()
            
        # Process frame with DeepStream-style analysis
        self.process_frame(frame)
            
        return Gst.FlowReturn.OK
    
    def process_frame(self, frame):
        """Process frame and print statistics"""
        self.frame_count += 1
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate frame statistics
        mean_intensity = float(np.mean(gray))
        std_intensity = float(np.std(gray))
        min_intensity = float(np.min(gray))
        max_intensity = float(np.max(gray))
        
        # Calculate real-time FPS
        current_time = time.time()
        time_diff = current_time - self.last_fps_time
        
        if time_diff >= 1.0:  # Update FPS every second
            fps = (self.frame_count - self.last_fps_count) / time_diff
            self.last_fps_time = current_time
            self.last_fps_count = self.frame_count
        else:
            # Use average FPS for display
            elapsed_time = current_time - self.start_time
            fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        
        # Print frame statistics
        print(f"🧠 Frame #{self.frame_count:06d} | "
              f"Size: {frame.shape[1]}x{frame.shape[0]} | "
              f"FPS: {fps:.2f} | "
              f"Intensity: μ={mean_intensity:.2f} σ={std_intensity:.2f} "
              f"[{min_intensity:.0f}-{max_intensity:.0f}]")
        
        # Optional: Save frame every 100 frames for debugging (DISABLED)
        # if self.frame_count % 100 == 0:
        #     filename = f"frame_{self.frame_count:06d}.jpg"
        #     cv2.imwrite(filename, frame)
        #     print(f"💾 Saved frame: {filename}")
    
    def setup_gstreamer_pipeline(self):
        """Setup GStreamer pipeline for RTSP/UDP consumption"""
        # Check if URL is RTSP or UDP
        if self.rtsp_url.startswith('rtsp://'):
            # RTSP source pipeline
            pipeline_str = f"""
            rtspsrc location={self.rtsp_url} latency=0 protocols=tcp !
            rtph264depay !
            h264parse !
            avdec_h264 !
            videoconvert !
            video/x-raw,format=BGR !
            appsink emit-signals=true max-buffers=1 drop=true sync=false
            """
        else:
            # UDP RTP source pipeline (fallback)
            pipeline_str = f"""
            udpsrc port=8554 !
            application/x-rtp,media=video,clock-rate=90000,encoding-name=H264 !
            rtph264depay !
            h264parse !
            avdec_h264 !
            videoconvert !
            video/x-raw,format=BGR !
            appsink emit-signals=true max-buffers=1 drop=true sync=false
            """
        
        logger.info(f"Setting up RTSP consumer pipeline: {pipeline_str.strip()}")
        self.pipeline = Gst.parse_launch(pipeline_str)
        
        # Get appsink element
        appsink = self.pipeline.get_by_interface(GstApp.AppSink)
        if not appsink:
            appsink = self.pipeline.get_by_name("appsink0")
            
        if not appsink:
            raise RuntimeError("Could not find appsink element in pipeline")
            
        appsink.connect("new-sample", self.on_new_sample)
        return self.pipeline
    
    def start_gstreamer(self):
        """Start the GStreamer pipeline in a separate thread"""
        def gst_thread():
            try:
                self.pipeline.set_state(Gst.State.PLAYING)
                loop = GLib.MainLoop()
                self.running = True
                loop.run()
            except Exception as e:
                logger.error(f"GStreamer error: {e}")
                self.running = False
        
        gst_thread_obj = threading.Thread(target=gst_thread, daemon=True)
        gst_thread_obj.start()
        return gst_thread_obj
    
    def run(self):
        """Run the RTSP consumer"""
        try:
            # Setup GStreamer pipeline
            self.setup_gstreamer_pipeline()
            
            # Start GStreamer in background
            logger.info("Starting RTSP consumer...")
            self.start_gstreamer()
            
            # Give pipeline time to initialize
            time.sleep(2)
            
            logger.info("=" * 60)
            logger.info("🎥 RTSP CONSUMER CONNECTED")
            logger.info("=" * 60)
            logger.info(f"Stream URL: {self.rtsp_url}")
            logger.info("Processing frames... Press Ctrl+C to stop")
            logger.info("=" * 60)
            
            # Keep running and print periodic stats
            while self.running:
                time.sleep(5)
                if self.frame_count > 0:
                    elapsed = time.time() - self.start_time
                    avg_fps = self.frame_count / elapsed
                    print(f"📊 Consumer Stats: {self.frame_count} frames processed, "
                          f"Avg FPS: {avg_fps:.2f}, Runtime: {elapsed:.1f}s")
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
        except Exception as e:
            logger.error(f"Error: {e}")
            self.stop()
    
    def stop(self):
        """Stop the pipeline and cleanup"""
        self.running = False
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            
        logger.info("RTSP Consumer stopped")

def main():
    """Main function"""
    import os
    import sys
    
    # Force immediate output
    print("=" * 60)
    print("🚀 RTSP CONSUMER STARTING")
    print("=" * 60)
    sys.stdout.flush()
    
    # Get URL from environment variable first, then command line args
    env_url = os.getenv('RTSP_URL')
    
    parser = argparse.ArgumentParser(description='RTSP Consumer')
    parser.add_argument('--url', default=env_url,
                       help='RTSP/UDP stream URL (default: RTSP_URL env var)')
    
    args = parser.parse_args()
    
    # If no URL provided via args or env, use default
    if not args.url:
        args.url = 'udp://100.94.31.62:8554'  # Updated to correct IP
    
    # Debug: Print the URL being used with proper logging
    print(f"🔗 Using stream URL: {args.url}")
    print(f"🔗 Environment RTSP_URL: {os.getenv('RTSP_URL', 'NOT SET')}")
    print(f"🔗 Command line args: {sys.argv}")
    print(f"🔗 Working directory: {os.getcwd()}")
    print("=" * 60)
    sys.stdout.flush()
    
    # Handle case where script path is passed as argument
    if args.url and args.url.startswith('/app/'):
        print(f"⚠️  Detected script path as URL: {args.url}")
        print("🔄 Falling back to environment variable...")
        env_url = os.getenv('RTSP_URL')
        if env_url:
            args.url = env_url
            print(f"✅ Using environment URL: {args.url}")
        else:
            args.url = 'udp://100.94.31.62:8554'
            print(f"✅ Using default URL: {args.url}")
    
    # Validate URL format
    if not args.url:
        print("❌ No URL provided")
        print("Set RTSP_URL environment variable or use --url argument")
        sys.exit(1)
    
    if not (args.url.startswith('rtsp://') or args.url.startswith('udp://')):
        print(f"❌ Invalid URL format: {args.url}")
        print(f"❌ Expected format: rtsp://host:port/path or udp://host:port")
        sys.exit(1)
    
    print(f"✅ URL validation passed: {args.url}")
    sys.stdout.flush()
    
    # Create RTSP consumer instance
    consumer = RTSPConsumer(rtsp_url=args.url)
    
    # Run the consumer
    consumer.run()

if __name__ == "__main__":
    main()
