#!/usr/bin/env python3
"""
RTSP Producer
Captures video from DeepStream pipeline and streams it via RTSP server
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

class RTSPProducer:
    def __init__(self, rtsp_port=8554, rtsp_path="/test"):
        self.rtsp_port = rtsp_port
        self.rtsp_path = rtsp_path
        self.frame = None
        self.lock = threading.Lock()
        self.pipeline = None
        self.running = False
        self.frame_count = 0
        self.start_time = time.time()
        
    def get_local_ip(self):
        """Get local IP address for network access"""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception:
            return "127.0.0.1"
    
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
            
        self.frame_count += 1
        
        # Print basic frame info every 30 frames
        if self.frame_count % 30 == 0:
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            print(f"📹 Frame #{self.frame_count:06d} | Size: {width}x{height} | FPS: {fps:.2f}")
            
        return Gst.FlowReturn.OK
    
    def setup_gstreamer_pipeline(self, source_type="v4l2", device="/dev/video4"):
        """Setup GStreamer pipeline for video capture and RTSP streaming"""
        if source_type == "v4l2":
            # V4L2 source (RealSense camera) with RTSP streaming
            pipeline_str = f"""
            v4l2src device={device} io-mode=2 !
            video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 !
            videoconvert !
            video/x-raw,format=I420 !
            x264enc tune=zerolatency bitrate=2000 !
            rtph264pay name=pay0 pt=96 !
            udpsink host=127.0.0.1 port=5004
            """
        elif source_type == "deepstream":
            # DeepStream pipeline with RTSP streaming
            pipeline_str = f"""
            nvarguscamerasrc !
            video/x-raw(memory:NVMM),width=640,height=480,format=NV12,framerate=30/1 !
            nvvidconv !
            video/x-raw,format=I420 !
            nvv4l2h264enc bitrate=2000 !
            h264parse !
            rtph264pay name=pay0 pt=96 !
            udpsink host=127.0.0.1 port=5004
            """
        else:
            raise ValueError(f"Unknown source type: {source_type}")
            
        logger.info(f"Setting up GStreamer pipeline: {pipeline_str.strip()}")
        self.pipeline = Gst.parse_launch(pipeline_str)
        return self.pipeline
    
    def start_rtsp_server(self):
        """Start RTSP server using GStreamer's rtsp-server"""
        # Create RTSP server configuration
        rtsp_config = f"""
        (rtsp-server)
        protocols tcp
        port {self.rtsp_port}
        mount-points {self.rtsp_path}
        """
        
        # Write config to file
        config_file = "/tmp/rtsp-server.conf"
        with open(config_file, 'w') as f:
            f.write(rtsp_config)
        
        # Start RTSP server
        cmd = [
            "gst-rtsp-server",
            "--config", config_file,
            "--port", str(self.rtsp_port)
        ]
        
        logger.info(f"Starting RTSP server: {' '.join(cmd)}")
        try:
            self.rtsp_server_process = subprocess.Popen(cmd)
        except FileNotFoundError:
            logger.warning("gst-rtsp-server not found, trying alternative approach...")
            self.start_alternative_rtsp_server()
            return
        
        # Give server time to start
        time.sleep(2)
        
        # Start the media pipeline
        media_cmd = [
            "gst-launch-1.0",
            "udpsrc", "port=5004",
            "!", "application/x-rtp,media=video,clock-rate=90000,encoding-name=H264",
            "!", "rtph264depay",
            "!", "h264parse",
            "!", "rtspclientsink", f"location=rtsp://127.0.0.1:{self.rtsp_port}{self.rtsp_path}"
        ]
        
        logger.info(f"Starting media pipeline: {' '.join(media_cmd)}")
        self.media_process = subprocess.Popen(media_cmd)
    
    def start_alternative_rtsp_server(self):
        """Alternative RTSP server using tcpserversink"""
        logger.info("Using alternative RTSP approach with tcpserversink")
        
        # Create a simple RTSP server using tcpserversink
        rtsp_cmd = [
            "gst-launch-1.0",
            "tcpserversink", f"host=0.0.0.0", f"port={self.rtsp_port}",
            "!", "rtspclientsink", f"location=rtsp://0.0.0.0:{self.rtsp_port}{self.rtsp_path}"
        ]
        
        logger.info(f"Starting alternative RTSP server: {' '.join(rtsp_cmd)}")
        self.rtsp_server_process = subprocess.Popen(rtsp_cmd)
    
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
        """Run the RTSP producer"""
        try:
            # Setup GStreamer pipeline
            self.setup_gstreamer_pipeline(source_type, device)
            
            # Start RTSP server
            logger.info("Starting RTSP server...")
            self.start_rtsp_server()
            
            # Start GStreamer in background
            logger.info("Starting GStreamer pipeline...")
            self.start_gstreamer()
            
            # Give everything time to initialize
            time.sleep(3)
            
            # Get local IP for network access
            local_ip = self.get_local_ip()
            
            rtsp_url_local = f"rtsp://127.0.0.1:{self.rtsp_port}{self.rtsp_path}"
            rtsp_url_network = f"rtsp://{local_ip}:{self.rtsp_port}{self.rtsp_path}"
            
            logger.info("=" * 60)
            logger.info("🎥 RTSP STREAM READY")
            logger.info("=" * 60)
            logger.info(f"Local URL:  {rtsp_url_local}")
            logger.info(f"Network URL: {rtsp_url_network}")
            logger.info("=" * 60)
            logger.info("Use VLC or other RTSP client to view the stream")
            logger.info("For Tailscale access, use the Network URL")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)
            
            # Keep running and print periodic stats
            while self.running:
                time.sleep(10)
                if self.frame_count > 0:
                    elapsed = time.time() - self.start_time
                    avg_fps = self.frame_count / elapsed
                    print(f"📊 Producer Stats: {self.frame_count} frames streamed, "
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
            
        if hasattr(self, 'rtsp_server_process') and self.rtsp_server_process:
            self.rtsp_server_process.terminate()
            self.rtsp_server_process.wait()
            
        if hasattr(self, 'media_process') and self.media_process:
            self.media_process.terminate()
            self.media_process.wait()
            
        logger.info("RTSP Producer stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("Received interrupt signal")
    sys.exit(0)

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RTSP Producer')
    parser.add_argument('--port', type=int, default=8554, help='RTSP port (default: 8554)')
    parser.add_argument('--path', default='/test', help='RTSP path (default: /test)')
    parser.add_argument('--source', choices=['v4l2', 'deepstream'], default='v4l2',
                       help='Video source type (default: v4l2)')
    parser.add_argument('--device', default='/dev/video4', 
                       help='Video device path (default: /dev/video4)')
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create RTSP producer instance
    producer = RTSPProducer(rtsp_port=args.port, rtsp_path=args.path)
    
    # Run the producer
    producer.run(source_type=args.source, device=args.device)

if __name__ == "__main__":
    main()
