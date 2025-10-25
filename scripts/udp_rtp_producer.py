#!/usr/bin/env python3
"""
Simple UDP RTP Producer
Captures video and streams it via UDP RTP
"""

import gi
import cv2
import numpy as np
import threading
import time
import logging
import subprocess
import os
import signal
import sys
import socket

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib, GstApp

# Initialize GStreamer
Gst.init(None)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UDPRTPProducer:
    def __init__(self, udp_port=8554, host="0.0.0.0"):
        self.udp_port = udp_port
        self.host = host
        self.frame = None
        self.lock = threading.Lock()
        self.pipeline = None
        self.running = False
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_time = time.time()
        self.last_fps_count = 0
        
    def on_frame_probe(self, pad, info):
        """Callback to count frames and calculate FPS"""
        self.frame_count += 1
        
        # Calculate real-time FPS
        current_time = time.time()
        time_diff = current_time - self.last_fps_time
        
        if time_diff >= 1.0:  # Update FPS every second
            fps = (self.frame_count - self.last_fps_count) / time_diff
            self.last_fps_time = current_time
            self.last_fps_count = self.frame_count
            
            # Print FPS stats
            elapsed = current_time - self.start_time
            avg_fps = self.frame_count / elapsed
            print(f"🎥 Producer Frame #{self.frame_count:06d} | "
                  f"Real-time FPS: {fps:.2f} | "
                  f"Avg FPS: {avg_fps:.2f} | "
                  f"Runtime: {elapsed:.1f}s")
            sys.stdout.flush()
        
        return Gst.PadProbeReturn.OK
        
    def get_local_ip(self):
        """Get local IP address for network access"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def setup_gstreamer_pipeline(self, source_type="v4l2", device="/dev/video4"):
        """Setup GStreamer pipeline for video capture and UDP RTP streaming"""
        if source_type == "v4l2":
            # V4L2 source with UDP RTP streaming and frame counting
            pipeline_str = f"""
            v4l2src device={device} io-mode=2 !
            video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 !
            videoconvert !
            video/x-raw,format=I420 !
            identity name=frame_counter !
            x264enc tune=zerolatency bitrate=2000 !
            rtph264pay name=pay0 pt=96 !
            udpsink host={self.host} port={self.udp_port}
            """
        elif source_type == "deepstream":
            # DeepStream pipeline with UDP RTP streaming and frame counting
            pipeline_str = f"""
            nvarguscamerasrc !
            video/x-raw(memory:NVMM),width=640,height=480,format=NV12,framerate=30/1 !
            nvvidconv !
            video/x-raw,format=I420 !
            identity name=frame_counter !
            nvv4l2h264enc bitrate=2000 !
            h264parse !
            rtph264pay name=pay0 pt=96 !
            udpsink host={self.host} port={self.udp_port}
            """
        else:
            raise ValueError(f"Unknown source type: {source_type}")
            
        logger.info(f"Setting up GStreamer pipeline: {pipeline_str.strip()}")
        self.pipeline = Gst.parse_launch(pipeline_str)
        
        # Add probe to identity element for frame counting
        identity = self.pipeline.get_by_name("frame_counter")
        if identity:
            pad = identity.get_static_pad("src")
            if pad:
                pad.add_probe(Gst.PadProbeType.BUFFER, self.on_frame_probe)
                logger.info("Added frame counting probe")
        
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
    
    def run(self, source_type="v4l2", device="/dev/video4"):
        """Run the UDP RTP producer"""
        try:
            # Setup GStreamer pipeline
            self.setup_gstreamer_pipeline(source_type, device)
            
            # Start GStreamer in background
            logger.info("Starting UDP RTP producer...")
            self.start_gstreamer()
            
            # Give everything time to initialize
            time.sleep(3)
            
            # Get local IP for network access
            local_ip = self.get_local_ip()
            
            udp_url_local = f"udp://127.0.0.1:{self.udp_port}"
            udp_url_network = f"udp://{local_ip}:{self.udp_port}"
            
            logger.info("=" * 60)
            logger.info("🎥 UDP RTP STREAM READY")
            logger.info("=" * 60)
            logger.info(f"Local URL:  {udp_url_local}")
            logger.info(f"Network URL: {udp_url_network}")
            logger.info("=" * 60)
            logger.info("Use GStreamer consumer to view the stream")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)
            
            # Keep running (FPS stats are printed by frame probe callback)
            while self.running:
                time.sleep(1)
                
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
            
        logger.info("UDP RTP Producer stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("Received interrupt signal")
    sys.exit(0)

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='UDP RTP Producer')
    parser.add_argument('--port', type=int, default=8554, help='UDP port (default: 8554)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--source', choices=['v4l2', 'deepstream'], default='v4l2',
                       help='Video source type (default: v4l2)')
    parser.add_argument('--device', default='/dev/video4', 
                       help='Video device path (default: /dev/video4)')
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create UDP RTP producer instance
    producer = UDPRTPProducer(udp_port=args.port, host=args.host)
    
    # Run the producer
    producer.run(source_type=args.source, device=args.device)

if __name__ == "__main__":
    main()
