#!/usr/bin/env python3
"""
UDP RTP Consumer
Receives UDP RTP streams and processes frames with DeepStream
Uses proper Python GStreamer pipeline construction (no parse_launch)
Matches the producer's style
"""

import gi
import cv2
import numpy as np
import threading
import time
import logging
import sys
import os
import base64
import requests
from collections import deque

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UDPRTPConsumer:
    def __init__(self, url):
        self.url = url
        self.frame = None
        self.lock = threading.Lock()
        self.pipeline = None
        self.loop = None
        self.running = False
        self.frame_count = 0
        self.start_time = None
        self.last_fps_time = time.time()
        self.last_fps_count = 0
        self.last_frame_time = time.time()
        self.stream_timeout = 5.0  # seconds without frames before considering stream dead
        
        # VJEPA2 service integration
        self.vjepa_service_url = vjepa_service_url or os.getenv(
            'VJEPA_SERVICE_URL', 
            'http://localhost:8000'
        )
        self.frame_buffer = deque(maxlen=16)  # Store 16 frames for VJEPA2 (frames_per_clip)
        self.frames_per_clip = 16
        self.clips_sent = 0
        
    def on_new_sample(self, sink):
        """Callback function for new video samples from GStreamer"""
        sample = sink.emit("pull-sample")
        if not sample:
            logger.warning("No sample received from appsink")
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
        self.last_frame_time = time.time()
        
        # Initialize start time on first frame
        if self.start_time is None:
            self.start_time = time.time()
        
        # Add frame to buffer for VJEPA2 inference
        self.frame_buffer.append(frame.copy())
        
        # When buffer is full, send to VJEPA2 service
        if len(self.frame_buffer) == self.frames_per_clip:
            self.send_clip_to_vjepa()
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate frame statistics
        mean_intensity = float(np.mean(gray))
        std_intensity = float(np.std(gray))
        min_intensity = float(np.min(gray))
        max_intensity = float(np.max(gray))
        
        # Show stats every 30 frames (~1 second at 30fps)
        if self.frame_count % 30 == 0:
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            
            # Print inline update (like producer)
            sys.stdout.write(f"\r🧠 Frame #{self.frame_count:06d} | "
                           f"Size: {frame.shape[1]}x{frame.shape[0]} | "
                           f"FPS: {fps:5.1f} | "
                           f"Intensity: μ={mean_intensity:.2f} σ={std_intensity:.2f} "
                           f"[{min_intensity:.0f}-{max_intensity:.0f}] | "
                           f"Clips: {self.clips_sent}")
            sys.stdout.flush()
    
    def send_clip_to_vjepa(self):
        """Send batched clip to vjepa2-service (non-blocking)"""
        if not self.vjepa_service_url:
            return
        
        # Copy frames from buffer (in case buffer is modified during encoding)
        frames_to_send = list(self.frame_buffer)
        
        def send_async():
            """Send clip in background thread to avoid blocking pipeline"""
            try:
                # Encode frames to base64 JPEG
                frames_b64 = []
                for frame in frames_to_send:
                    # Encode frame as JPEG then base64
                    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    if not success:
                        logger.warning("Failed to encode frame to JPEG")
                        continue
                    frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    frames_b64.append(frame_b64)
                
                if len(frames_b64) != self.frames_per_clip:
                    logger.warning(f"Expected {self.frames_per_clip} frames, got {len(frames_b64)}")
                    return
                
                # Send to service
                response = requests.post(
                    f"{self.vjepa_service_url}/api/v1/infer",
                    json={
                        "frames": frames_b64,
                        "width": frames_to_send[0].shape[1],
                        "height": frames_to_send[0].shape[0],
                        "format": "BGR"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    results = response.json()
                    predictions = results.get('predictions', [])
                    if predictions:
                        top_pred = predictions[0]
                        logger.info(
                            f"VJEPA2 Prediction: {top_pred.get('label', 'unknown')} "
                            f"({top_pred.get('confidence', 0.0):.2f})"
                        )
                    self.clips_sent += 1
                else:
                    logger.warning(
                        f"VJEPA2 service returned status {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to send clip to VJEPA2 service: {e}")
            except Exception as e:
                logger.error(f"Error in send_clip_to_vjepa: {e}", exc_info=True)
        
        # Run in background thread to avoid blocking pipeline
        thread = threading.Thread(target=send_async, daemon=True)
        thread.start()
    
    def bus_call(self, bus, message, loop):
        """Handle GStreamer bus messages"""
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("\nEnd-of-stream\n")
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            sys.stderr.write(f"\nWarning: {err}: {debug}\n")
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write(f"\nError: {err}: {debug}\n")
            loop.quit()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                logger.info(f"Pipeline state: {old_state.value_nick} → {new_state.value_nick}")
        elif t == Gst.MessageType.STREAM_START:
            logger.info("Stream started")
        return True
    
    def check_stream_health(self):
        """Check if stream is still active by monitoring frame reception"""
        current_time = time.time()
        time_since_last_frame = current_time - self.last_frame_time
        
        if time_since_last_frame > self.stream_timeout:
            if self.frame_count > 0:
                logger.warning(f"\n⚠️  No frames received for {time_since_last_frame:.1f}s - stream may be dead")
            else:
                logger.warning(f"\n⚠️  No frames received yet after {time_since_last_frame:.1f}s")
            return False
        
        return True
    
    def setup_gstreamer_pipeline(self):
        """Setup GStreamer pipeline for UDP consumption using proper Python API"""
        print("=" * 60)
        print("DeepStream Consumer - Building Pipeline")
        print("=" * 60)
        
        # Parse URL for port
        if self.url.startswith('udp://'):
            url_parts = self.url[6:]  # Remove 'udp://'
            if ':' in url_parts:
                host, port_str = url_parts.split(':', 1)
                port = int(port_str)
            else:
                host = url_parts
                port = 8554
        else:
            host = "127.0.0.1"
            port = 8554
        
        logger.info(f"UDP connection: host={host}, port={port}")
        
        # Create Pipeline
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            logger.error("Unable to create Pipeline")
            return False
        
        # STEP 1: UDP source
        print("Creating udpsrc")
        source = Gst.ElementFactory.make("udpsrc", "source")
        if not source:
            logger.error("Unable to create udpsrc")
            return False
        source.set_property('port', port)
        
        # STEP 2: RTP caps filter
        print("Creating capsfilter (RTP)")
        caps_rtp = Gst.ElementFactory.make("capsfilter", "caps-rtp")
        if not caps_rtp:
            logger.error("Unable to create capsfilter")
            return False
        caps_rtp.set_property('caps', Gst.Caps.from_string("application/x-rtp,encoding-name=H264,payload=96"))
        
        # STEP 3: RTP H.264 depayloader
        print("Creating rtph264depay")
        rtpdepay = Gst.ElementFactory.make("rtph264depay", "rtpdepay")
        if not rtpdepay:
            logger.error("Unable to create rtph264depay")
            return False
        
        # STEP 4: H.264 parser
        print("Creating h264parse")
        h264parse = Gst.ElementFactory.make("h264parse", "parser")
        if not h264parse:
            logger.error("Unable to create h264parse")
            return False
        
        # STEP 5: H.264 decoder
        print("Creating avdec_h264")
        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        if not decoder:
            logger.error("Unable to create avdec_h264")
            return False
        
        # STEP 6: Convert to GRAY8 (to match what producer sends)
        print("Creating videoconvert (to grayscale)")
        vidconv1 = Gst.ElementFactory.make("videoconvert", "conv-gray")
        if not vidconv1:
            logger.error("Unable to create videoconvert")
            return False
        
        # Grayscale caps
        caps_gray = Gst.ElementFactory.make("capsfilter", "caps-gray")
        if not caps_gray:
            logger.error("Unable to create capsfilter")
            return False
        caps_gray.set_property('caps', Gst.Caps.from_string("video/x-raw,format=GRAY8"))
        
        # STEP 7: Convert to BGR for processing
        print("Creating videoconvert (to BGR)")
        vidconv2 = Gst.ElementFactory.make("videoconvert", "conv-bgr")
        if not vidconv2:
            logger.error("Unable to create videoconvert")
            return False
        
        # BGR caps
        caps_bgr = Gst.ElementFactory.make("capsfilter", "caps-bgr")
        if not caps_bgr:
            logger.error("Unable to create capsfilter")
            return False
        caps_bgr.set_property('caps', Gst.Caps.from_string("video/x-raw,format=BGR"))
        
        # STEP 8: App sink
        print("Creating appsink")
        sink = Gst.ElementFactory.make("appsink", "sink")
        if not sink:
            logger.error("Unable to create appsink")
            return False
        sink.set_property('emit-signals', True)
        sink.set_property('max-buffers', 1)
        sink.set_property('drop', True)
        sink.set_property('sync', False)
        
        # Add all elements to pipeline
        print("Adding elements to pipeline")
        self.pipeline.add(source)
        self.pipeline.add(caps_rtp)
        self.pipeline.add(rtpdepay)
        self.pipeline.add(h264parse)
        self.pipeline.add(decoder)
        self.pipeline.add(vidconv1)
        self.pipeline.add(caps_gray)
        self.pipeline.add(vidconv2)
        self.pipeline.add(caps_bgr)
        self.pipeline.add(sink)
        
        # Link all elements
        print("Linking elements")
        if not source.link(caps_rtp):
            logger.error("Failed to link source → caps_rtp")
            return False
        if not caps_rtp.link(rtpdepay):
            logger.error("Failed to link caps_rtp → rtpdepay")
            return False
        if not rtpdepay.link(h264parse):
            logger.error("Failed to link rtpdepay → h264parse")
            return False
        if not h264parse.link(decoder):
            logger.error("Failed to link h264parse → decoder")
            return False
        if not decoder.link(vidconv1):
            logger.error("Failed to link decoder → vidconv1")
            return False
        if not vidconv1.link(caps_gray):
            logger.error("Failed to link vidconv1 → caps_gray")
            return False
        if not caps_gray.link(vidconv2):
            logger.error("Failed to link caps_gray → vidconv2")
            return False
        if not vidconv2.link(caps_bgr):
            logger.error("Failed to link vidconv2 → caps_bgr")
            return False
        if not caps_bgr.link(sink):
            logger.error("Failed to link caps_bgr → sink")
            return False
        
        print("=" * 60)
        print("Pipeline Ready!")
        print(f"  1. UDP Source (port {port})")
        print("  2. RTP H.264 Depayload")
        print("  3. H.264 Parse & Decode")
        print("  4. Convert to GRAY8 (match producer)")
        print("  5. Convert to BGR (for processing)")
        print("  6. AppSink (for frame callback)")
        print("=" * 60)
        
        # Connect appsink callback
        sink.connect("new-sample", self.on_new_sample)
        logger.info("✓ Connected appsink callback")
        logger.info(f"✓ Appsink properties: max-buffers={sink.get_property('max-buffers')}, "
                   f"drop={sink.get_property('drop')}, sync={sink.get_property('sync')}")
        
        return True
    
    def run(self):
        """Run the UDP RTP consumer"""
        try:
            # Setup GStreamer pipeline
            if not self.setup_gstreamer_pipeline():
                logger.error("Failed to setup pipeline")
                return
            
            # Create event loop
            self.loop = GLib.MainLoop()
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.bus_call, self.loop)
            
            # Start pipeline
            logger.info("Starting pipeline...")
            self.pipeline.set_state(Gst.State.PLAYING)
            self.running = True
            
            print("\n" + "=" * 60)
            print("🎥 CONSUMER RECEIVING FROM PRODUCER")
            print("=" * 60)
            print(f"Stream URL: {self.url}")
            print("Format: Grayscale 240x240 → BGR for analysis")
            print("=" * 60)
            print("Press Ctrl+C to stop")
            print("=" * 60 + "\n")
            
            try:
                self.loop.run()
            except KeyboardInterrupt:
                print("\n\nStopping...")
                pass
                
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the pipeline and cleanup"""
        self.running = False
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        # Print final stats
        if self.frame_count > 0 and self.start_time:
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed if elapsed > 0 else 0
            print(f"\n📊 Final Stats: {self.frame_count} frames in {elapsed:.1f}s ({fps:.1f} fps)")
            
        logger.info("Consumer stopped")

def main():
    """Main function"""
    import os
    
    # Force immediate output
    print("=" * 60)
    print("🚀 UDP RTP CONSUMER STARTING")
    print("=" * 60)
    sys.stdout.flush()
    
    # Get URL from environment variable
    env_url = os.getenv('RTSP_URL')
    
    # Use environment variable or default
    if env_url:
        url = env_url
        print(f"✅ Using environment URL: {url}")
    else:
        url = 'udp://127.0.0.1:8554'
        print(f"✅ Using default URL: {url}")
    
    # Debug info
    print(f"🔗 Using stream URL: {url}")
    print(f"🔗 Environment RTSP_URL: {os.getenv('RTSP_URL', 'NOT SET')}")
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
    
    # Create UDP RTP consumer instance
    consumer = UDPRTPConsumer(url=url)
    
    # Run the consumer
    consumer.run()

if __name__ == "__main__":
    main()

