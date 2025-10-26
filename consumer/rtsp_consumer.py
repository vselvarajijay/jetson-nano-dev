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
import sys

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

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
        self.last_frame_time = time.time()
        self.stream_timeout = 5.0  # seconds without frames before considering stream dead
        
    def on_new_sample(self, sink):
        """Callback function for new video samples from GStreamer"""
        logger.info("🎬 on_new_sample callback called!")
        sample = sink.emit("pull-sample")
        if not sample:
            logger.warning("No sample received from appsink")
            return Gst.FlowReturn.ERROR
        
        logger.info(f"✅ Received sample: {sample}")
            
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
        self.last_frame_time = time.time()  # Update last frame time
        
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
        sys.stdout.flush()
        
        # Optional: Save frame every 100 frames for debugging (DISABLED)
        # if self.frame_count % 100 == 0:
        #     filename = f"frame_{self.frame_count:06d}.jpg"
        #     cv2.imwrite(filename, frame)
        #     print(f"💾 Saved frame: {filename}")
    
    def on_bus_message(self, bus, message):
        """Handle GStreamer bus messages for debugging"""
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"GStreamer Error: {err}")
            logger.error(f"Debug info: {debug}")
        elif message.type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"GStreamer Warning: {warn}")
            logger.warning(f"Debug info: {debug}")
        elif message.type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, pending_state = message.parse_state_changed()
            if message.src == self.pipeline:
                logger.info(f"Pipeline state changed: {old_state.value_nick} -> {new_state.value_nick}")
        elif message.type == Gst.MessageType.STREAM_START:
            logger.info("Stream started")
        elif message.type == Gst.MessageType.EOS:
            logger.info("End of stream")
    
    def check_stream_health(self):
        """Check if stream is still active by monitoring frame reception"""
        current_time = time.time()
        time_since_last_frame = current_time - self.last_frame_time
        
        if time_since_last_frame > self.stream_timeout:
            if self.frame_count > 0:
                logger.warning(f"⚠️  No frames received for {time_since_last_frame:.1f}s - stream may be dead")
                logger.warning(f"   Last frame was #{self.frame_count} at {self.last_frame_time:.1f}")
                logger.warning(f"   Current time: {current_time:.1f}")
            else:
                logger.warning(f"⚠️  No frames received yet after {time_since_last_frame:.1f}s")
                logger.warning(f"   Producer may not be running or network issue")
            return False
        
        return True
    
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
            # UDP RTP source pipeline - parse URL for host and port
            if self.rtsp_url.startswith('udp://'):
                # Parse UDP URL: udp://host:port
                url_parts = self.rtsp_url[6:]  # Remove 'udp://'
                if ':' in url_parts:
                    host, port = url_parts.split(':', 1)
                else:
                    host = url_parts
                    port = "8554"
            else:
                host = "127.0.0.1"
                port = "8554"
            
            logger.info(f"UDP connection: host={host}, port={port}")
            
            pipeline_str = f"""
            udpsrc port={port} address={host} !
            application/x-rtp,encoding-name=H264,payload=96 !
            rtph264depay !
            h264parse !
            avdec_h264 !
            videoconvert !
            video/x-raw,format=GRAY8 !
            videoconvert !
            video/x-raw,format=BGR !
            appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false
            """
        
        logger.info(f"Setting up RTSP consumer pipeline: {pipeline_str.strip()}")
        self.pipeline = Gst.parse_launch(pipeline_str)
        
        # Add bus message handler for debugging
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        
        # Get appsink element
        appsink = self.pipeline.get_by_name("sink")
        if not appsink:
            raise RuntimeError("Could not find appsink element 'sink' in pipeline")
            
        appsink.connect("new-sample", self.on_new_sample)
        logger.info("Connected appsink callback")
        logger.info(f"Appsink properties: max-buffers={appsink.get_property('max-buffers')}, drop={appsink.get_property('drop')}, sync={appsink.get_property('sync')}")
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
            
            # Keep running and monitor stream health
            while self.running:
                time.sleep(2)  # Check more frequently
                
                # Check stream health
                if not self.check_stream_health():
                    logger.error("❌ Stream appears to be dead - stopping consumer")
                    break
                
                # Print periodic stats
                if self.frame_count > 0:
                    elapsed = time.time() - self.start_time
                    avg_fps = self.frame_count / elapsed
                    time_since_last = time.time() - self.last_frame_time
                    print(f"📊 Consumer Stats: {self.frame_count} frames processed, "
                          f"Avg FPS: {avg_fps:.2f}, Runtime: {elapsed:.1f}s, "
                          f"Last frame: {time_since_last:.1f}s ago")
                else:
                    elapsed = time.time() - self.start_time
                    print(f"⏳ Waiting for frames... Runtime: {elapsed:.1f}s")
                
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
    
    # Get URL from environment variable ONLY - ignore command line args completely
    env_url = os.getenv('RTSP_URL')
    
    # Use environment variable or default - NO command line parsing
    if env_url:
        url = env_url
        print(f"✅ Using environment URL: {url}")
    else:
        url = 'udp://127.0.0.1:8554'
        print(f"✅ Using default URL: {url}")
    
    # Debug: Print the URL being used with proper logging
    print(f"🔗 Using stream URL: {url}")
    print(f"🔗 Environment RTSP_URL: {os.getenv('RTSP_URL', 'NOT SET')}")
    print(f"🔗 Command line args: {sys.argv}")
    print(f"🔗 Working directory: {os.getcwd()}")
    print("=" * 60)
    sys.stdout.flush()
    
    # Validate URL format
    if not url:
        print("❌ No URL provided")
        print("Set RTSP_URL environment variable")
        sys.exit(1)
    
    if not (url.startswith('rtsp://') or url.startswith('udp://')):
        print(f"❌ Invalid URL format: {url}")
        print(f"❌ Expected format: rtsp://host:port/path or udp://host:port")
        sys.exit(1)
    
    print(f"✅ URL validation passed: {url}")
    sys.stdout.flush()
    
    # Create RTSP consumer instance
    consumer = RTSPConsumer(rtsp_url=url)
    
    # Run the consumer
    consumer.run()

if __name__ == "__main__":
    main()
