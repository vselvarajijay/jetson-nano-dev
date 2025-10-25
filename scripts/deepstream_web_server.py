#!/usr/bin/env python3
"""
DeepStream Web Server
A Python script that captures video from DeepStream pipeline and streams it via web server
"""

import gi
import cv2
import numpy as np
import threading
import time
from flask import Flask, render_template, Response
import logging

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib, GstApp

# Initialize GStreamer
Gst.init(None)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeepStreamWebServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.frame = None
        self.processed_frame = None
        self.lock = threading.Lock()
        self.pipeline = None
        self.running = False
        self.show_processed = False  # Flag to show processed stream
        
        # Setup Flask routes
        self.setup_routes()
        
    def setup_routes(self):
        """Setup Flask routes for the web server"""
        @self.app.route('/')
        def index():
            return render_template('index.html')
            
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.generate_frames(), 
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/processed_feed')
        def processed_feed():
            return Response(self.generate_processed_frames(), 
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/toggle_processed')
        def toggle_processed():
            self.show_processed = not self.show_processed
            return {'status': 'success', 'show_processed': self.show_processed}
    
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

        # Store original frame for web streaming
        with self.lock:
            self.frame = frame.copy()
            
            # Process frame (grayscale + stats) - same as your original code
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_intensity = float(np.mean(gray))
            
            # Convert grayscale back to 3-channel for web display
            processed_frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            
            # Add text overlay with intensity info
            cv2.putText(processed_frame, f"Mean Intensity: {mean_intensity:.2f}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            self.processed_frame = processed_frame
            
        # Print stats to console (like your original code)
        print(f"🧠 Frame processed: mean intensity={mean_intensity:.2f}")
            
        return Gst.FlowReturn.OK
    
    def generate_frames(self):
        """Generator function for original video frames"""
        while self.running:
            with self.lock:
                if self.frame is not None:
                    # Encode frame as JPEG
                    ret, buffer = cv2.imencode('.jpg', self.frame, 
                                             [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    def generate_processed_frames(self):
        """Generator function for processed video frames"""
        while self.running:
            with self.lock:
                if self.processed_frame is not None:
                    # Encode processed frame as JPEG
                    ret, buffer = cv2.imencode('.jpg', self.processed_frame, 
                                             [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    def setup_gstreamer_pipeline(self, source_type="v4l2", device="/dev/video4"):
        """Setup GStreamer pipeline for video capture"""
        if source_type == "v4l2":
            # V4L2 source (RealSense camera)
            pipeline_str = f"""
            v4l2src device={device} io-mode=2 !
            video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 !
            videoconvert !
            video/x-raw,format=BGR !
            appsink emit-signals=true max-buffers=1 drop=true sync=false
            """
        elif source_type == "deepstream":
            # DeepStream pipeline (if using DeepStream app)
            pipeline_str = """
            nvarguscamerasrc !
            video/x-raw(memory:NVMM),width=640,height=480,format=NV12,framerate=30/1 !
            nvvidconv !
            video/x-raw,format=BGRx !
            videoconvert !
            video/x-raw,format=BGR !
            appsink emit-signals=true max-buffers=1 drop=true sync=false
            """
        else:
            raise ValueError(f"Unknown source type: {source_type}")
            
        logger.info(f"Setting up GStreamer pipeline: {pipeline_str.strip()}")
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
    
    def run(self, source_type="v4l2", device="/dev/video4"):
        """Run the web server with DeepStream integration"""
        try:
            # Setup GStreamer pipeline
            self.setup_gstreamer_pipeline(source_type, device)
            
            # Start GStreamer in background
            logger.info("Starting GStreamer pipeline...")
            self.start_gstreamer()
            
            # Give GStreamer time to initialize
            time.sleep(2)
            
            # Start Flask web server
            logger.info(f"Starting web server on http://{self.host}:{self.port}")
            logger.info("Open your browser and navigate to the URL above to view the live stream")
            
            self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
            
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
        logger.info("Pipeline stopped")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DeepStream Web Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--source', choices=['v4l2', 'deepstream'], default='v4l2',
                       help='Video source type (default: v4l2)')
    parser.add_argument('--device', default='/dev/video4', 
                       help='Video device path (default: /dev/video4)')
    
    args = parser.parse_args()
    
    # Create templates directory if it doesn't exist
    import os
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    # Create web server instance
    server = DeepStreamWebServer(host=args.host, port=args.port)
    
    # Run the server
    server.run(source_type=args.source, device=args.device)

if __name__ == "__main__":
    main()
