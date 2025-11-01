#!/usr/bin/env python3
"""
Simple RealSense Video Clip Capture with Depth Data
Captures 3-second video clips with color (MP4) and depth data (numpy arrays).
Uses pyrealsense2 for depth, V4L2 fallback for color if needed.
"""

import os
import sys
import time

# Clean environment variables BEFORE importing pyrealsense2
# The error "global config-file/context: expecting an object; got ''"
# is caused by empty environment variables that pyrealsense2 reads during import
_empty_vars = [k for k, v in os.environ.items() if v == '']
if _empty_vars:
    for var in _empty_vars:
        os.environ.pop(var, None)
    print(f"⚠️  Cleaned {len(_empty_vars)} empty environment variable(s) before RealSense import")

# Clean up LD_PRELOAD if set to old library
if 'LD_PRELOAD' in os.environ:
    if 'librealsense2.so.2.54' in os.environ['LD_PRELOAD']:
        os.environ.pop('LD_PRELOAD', None)

# Ensure /usr/local/lib is in LD_LIBRARY_PATH for RSUSB backend (required on Jetson)
if '/usr/local/lib' not in os.environ.get('LD_LIBRARY_PATH', ''):
    current_path = os.environ.get('LD_LIBRARY_PATH', '')
    os.environ['LD_LIBRARY_PATH'] = f'/usr/local/lib:{current_path}' if current_path else '/usr/local/lib'

# Try to import pyrealsense2 for depth
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
    print("✓ pyrealsense2 available for depth data")
except Exception as e:
    REALSENSE_AVAILABLE = False
    print(f"⚠️  pyrealsense2 not available: {e}")
    print("  Will use V4L2 for color only (no depth)")

import cv2
import numpy as np
from datetime import datetime
import json
import threading
from queue import Queue

def find_camera():
    """Find working RGB color camera device - prioritize /dev/video4 (RGB)"""
    import numpy as np
    
    # User says /dev/video4 is RGB color - check it first
    # RealSense /dev/video4 supports YUYV format which is color (not IR)
    for device in ['/dev/video4', '/dev/video1', '/dev/video3', '/dev/video5']:
        try:
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None and len(frame.shape) == 3:
                    # Verify it's actually RGB color, not IR (IR has similar R,G,B values)
                    mean_r = np.mean(frame[:,:,0])
                    mean_g = np.mean(frame[:,:,1])
                    mean_b = np.mean(frame[:,:,2])
                    diff_rg = abs(mean_r - mean_g)
                    diff_gb = abs(mean_g - mean_b)
                    is_color = diff_rg > 10 or diff_gb > 10  # RGB should have noticeable differences
                    
                    # /dev/video4 with YUYV format is color - trust it even if R,G,B are similar
                    # (YUYV gets decoded as BGR, might appear grayscale if scene is monochrome)
                    if device == '/dev/video4' or is_color:
                        print(f"✓ Found RGB color camera at {device}")
                        cap.release()
                        return device
                cap.release()
        except:
            pass
    
    # Fallback: if no RGB found, warn and use /dev/video2 (but it's likely IR)
    print("⚠️  No RGB color camera found via V4L2 - falling back to /dev/video2 (may be IR)")
    for device in ['/dev/video2']:
        try:
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"⚠️  Using {device} (may be IR, not RGB)")
                    cap.release()
                    return device
                cap.release()
        except:
            pass
    return None

def capture_clip_realsense(duration=3.0, fps=15, quick_test=False):
    """Capture clip using RealSense SDK (gets both color and depth)"""
    # Create context and wait for backend
    ctx = rs.context()
    
    # For quick test, use shorter wait
    wait_time = 0.3 if quick_test else 1.0
    time.sleep(wait_time)
    
    # Query devices with retries (RSUSB backend needs time)
    devices = ctx.query_devices()
    max_retries = 1 if quick_test else 5  # Increase retries
    retry = 0
    while len(devices) == 0 and retry < max_retries:
        time.sleep(0.5 if quick_test else 1.0)
        try:
            devices = ctx.query_devices()
            if len(devices) > 0:
                break
        except Exception as e:
            if not quick_test:
                print(f"  Device query retry {retry + 1}/{max_retries}: {str(e)[:50]}")
        retry += 1
    
    if len(devices) == 0:
        if not quick_test:
            print("  ✗ No RealSense devices found after retries")
        return None, None, None
    
    # Create pipeline with context
    try:
        pipeline = rs.pipeline(ctx)
    except:
        pipeline = rs.pipeline()
    
    config = rs.config()
    
    # Try multiple initialization methods
    profile = None
    max_attempts = 1 if quick_test else 5  # Try multiple resolution/config combinations
    
    for attempt in range(max_attempts):
        try:
            # Stop any previous attempt
            try:
                pipeline.stop()
                time.sleep(0.1 if quick_test else 0.3)
            except:
                pass
            
            # Try different configs - prioritize highest resolution for color
            if attempt == 0:
                # Try highest resolution first (1920x1080 if available)
                try:
                    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                    config.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, fps)
                except:
                    # Fallback to 1280x720
                    config = rs.config()
                    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                    config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, fps)
            elif attempt == 1:
                # Try 1280x720
                config = rs.config()
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, fps)
            elif attempt == 2:
                # Try 640x480 (most compatible)
                config = rs.config()
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, fps)
            elif attempt == 3:
                # Try without explicit resolution (let SDK choose)
                config = rs.config()
                config.enable_stream(rs.stream.depth)
                config.enable_stream(rs.stream.color)
            elif attempt == 4:
                # Try with device selection
                config = rs.config()
                try:
                    config.enable_device(devices[0].get_info(rs.camera_info.serial_number))
                    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                    config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, fps)
                except:
                    config = rs.config()
                    config.enable_stream(rs.stream.depth)
                    config.enable_stream(rs.stream.color)
            else:
                # Fallback: enable all streams
                config = rs.config()
                config.enable_all_streams()
            
            # Start pipeline with longer timeout for first attempt
            if attempt == 0:
                # Give it more time on first attempt
                time.sleep(0.5)
            
            profile = pipeline.start(config)
            if not quick_test:
                print(f"  ✓ Pipeline started (attempt {attempt + 1})")
            break
            
        except Exception as e:
            if quick_test:
                # For quick test, fail immediately
                return None, None, None
            elif attempt < max_attempts - 1:
                print(f"  Attempt {attempt + 1} failed: {str(e)[:50]}...")
                time.sleep(0.5)  # Wait a bit longer between retries
            else:
                # All attempts failed
                error_msg = str(e)
                if "No device connected" in error_msg or "device" in error_msg.lower():
                    print(f"  ✗ RealSense SDK can't access device (known SDK bug)")
                return None, None, None
    
    if profile is None:
        return None, None, None
    
    # Get depth scale
    try:
        device = profile.get_device()
        depth_sensor = device.first_depth_sensor()
        depth_scale = depth_sensor.get_depth_scale()
    except:
        depth_scale = 0.001  # Default 1mm per unit
    
    # Alignment (align depth to color)
    align = rs.align(rs.stream.color)
    
    # Capture frames
    color_frames = []
    depth_frames = []
    timestamps = []
    
    expected_frames = int(duration * fps)
    frame_count = 0
    max_wait_time = 5.0  # seconds
    
    print(f"Capturing {duration}s clip ({expected_frames} frames)...", end=' ', flush=True)
    
    while frame_count < expected_frames:
        try:
            frames = pipeline.wait_for_frames(timeout_ms=int(max_wait_time * 1000))
            aligned = align.process(frames)
            
            depth_frame = aligned.get_depth_frame()
            color_frame = aligned.get_color_frame()
            
            if not depth_frame or not color_frame:
                continue
            
            # Convert to numpy
            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())
            
            # Depth to mm (uint16 depth values * scale * 1000 = mm)
            depth_mm = (depth_image.astype(np.float32) * depth_scale * 1000.0)
            
            color_frames.append(color_image.copy())
            depth_frames.append(depth_mm.copy())
            timestamps.append(time.time())
            
            frame_count += 1
            
            if frame_count % 10 == 0:
                progress = (frame_count / expected_frames) * 100
                print(f"{progress:.0f}%", end=' ', flush=True)
        except Exception as e:
            print(f"\n  ⚠️  Frame capture error: {str(e)[:50]}")
            break
    
    pipeline.stop()
    print(f"Done! ({len(color_frames)} frames)")
    
    return color_frames, depth_frames, timestamps

def read_z16_depth_frame(device_path='/dev/video0', width=256, height=144):
    """Read raw Z16 depth frame from V4L2 device using v4l2-ctl"""
    import subprocess
    import struct
    
    try:
        # Use v4l2-ctl to capture raw frame
        # Z16 format is 16-bit depth, so frame size = width * height * 2 bytes
        cmd = ['v4l2-ctl', '--device', device_path, '--stream-mmap', '--stream-count=1', '--stream-to=-']
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        
        if result.returncode == 0 and len(result.stdout) > 0:
            # Parse raw Z16 data
            frame_size = width * height * 2  # 2 bytes per pixel (16-bit)
            if len(result.stdout) >= frame_size:
                # Convert bytes to numpy array
                depth_data = np.frombuffer(result.stdout[:frame_size], dtype=np.uint16)
                depth_frame = depth_data.reshape((height, width))
                return depth_frame
        
        # Fallback: try reading via OpenCV (might not work but worth trying)
        cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
        if cap.isOpened():
            # Try to read as raw
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                # If it's grayscale, treat as depth
                if len(frame.shape) == 2:
                    return frame.astype(np.uint16) if frame.dtype != np.uint16 else frame
                elif len(frame.shape) == 3 and frame.shape[2] == 1:
                    return frame[:,:,0].astype(np.uint16) if frame.dtype != np.uint16 else frame[:,:,0]
    except:
        pass
    
    return None

def find_depth_device(exclude_device=None):
    """Try to find a V4L2 device that provides depth/IR data"""
    # RealSense typically exposes depth on /dev/video0 with Z16 format (16-bit depth)
    # Check if /dev/video0 exists and has Z16 format
    import os
    if os.path.exists('/dev/video0') and '/dev/video0' != exclude_device:
        # Try to read a test frame to verify it's depth
        test_frame = read_z16_depth_frame('/dev/video0')
        if test_frame is not None:
            print(f"  ✓ Found depth stream at /dev/video0 (Z16 format, {test_frame.shape})")
            return '/dev/video0'
    
    # Fallback: try other devices (excluding the one used for color)
    # Only check /dev/video2 if it's not being used for color
    for device in ['/dev/video2', '/dev/video1']:
        if device == exclude_device:
            continue
        try:
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Other devices might be IR/grayscale
                    if len(frame.shape) == 2 or (len(frame.shape) == 3 and frame.shape[2] == 1):
                        print(f"  ✓ Found potential depth/IR at {device}")
                        cap.release()
                        return device
                cap.release()
        except Exception as e:
            pass
    return None

def depth_reader_thread(depth_device_path, depth_queue, stop_event, width=256, height=144):
    """Background thread to continuously read depth frames"""
    use_raw_depth = (depth_device_path == '/dev/video0')
    
    while not stop_event.is_set():
        try:
            if use_raw_depth:
                depth_frame = read_z16_depth_frame(depth_device_path, width, height)
            else:
                # Would use OpenCV here if needed
                depth_frame = None
            
            if depth_frame is not None:
                # Non-blocking put - don't wait if queue is full
                try:
                    depth_queue.put_nowait((time.time(), depth_frame))
                except:
                    # Queue full - drop this frame, keep reading
                    pass
            time.sleep(0.01)  # Small delay between reads
        except:
            pass
    
    print("  Depth reader thread stopped")

def capture_clip_v4l2(color_cap, depth_cap, duration=3.0, fps=30, depth_device_path=None, save_queue=None):
    """Capture clip using V4L2 (color + optional depth) - non-blocking save"""
    color_frames = []
    depth_frames = []
    timestamps = []
    
    expected_frames = int(duration * fps)
    frame_count = 0
    
    print(f"Capturing {duration}s clip ({expected_frames} frames)...", end=' ', flush=True)
    
    # If we have depth device, start background reader thread
    depth_queue = None
    depth_thread = None
    stop_event = None
    
    use_raw_depth = (depth_device_path == '/dev/video0')
    if use_raw_depth:
        depth_queue = Queue(maxsize=10)  # Small buffer
        stop_event = threading.Event()
        depth_thread = threading.Thread(
            target=depth_reader_thread,
            args=(depth_device_path, depth_queue, stop_event),
            daemon=True
        )
        depth_thread.start()
    
    start_time = time.time()
    
    while frame_count < expected_frames:
        ret_color, color_frame = color_cap.read()
        if ret_color and color_frame is not None:
            color_frames.append(color_frame.copy())
            frame_time = time.time()
            timestamps.append(frame_time)
            
            # Try to get depth frame if available (non-blocking)
            depth_frame = None
            if depth_queue is not None:
                # Try to get latest depth frame from queue (non-blocking)
                latest_depth = None
                latest_time = 0
                # Drain queue to get most recent depth frame
                while not depth_queue.empty():
                    try:
                        depth_time, depth_data = depth_queue.get_nowait()
                        if depth_time <= frame_time and depth_time > latest_time:
                            latest_depth = depth_data
                            latest_time = depth_time
                    except:
                        break
                depth_frame = latest_depth
            
            elif depth_cap is not None:
                # Use OpenCV capture for other devices (non-blocking)
                ret_depth, depth_frame_raw = depth_cap.read()
                if ret_depth and depth_frame_raw is not None:
                    if len(depth_frame_raw.shape) == 3:
                        depth_frame = cv2.cvtColor(depth_frame_raw, cv2.COLOR_BGR2GRAY)
                    else:
                        depth_frame = depth_frame_raw.copy()
                    if depth_frame.dtype == np.uint8:
                        depth_frame = depth_frame.astype(np.uint16) * 256
            
            depth_frames.append(depth_frame)
            frame_count += 1
            
            if frame_count % 30 == 0:
                progress = (frame_count / expected_frames) * 100
                print(f"{progress:.0f}%", end=' ', flush=True)
        else:
            time.sleep(0.01)
    
    # Stop depth reader thread
    if stop_event is not None:
        stop_event.set()
        if depth_thread is not None:
            depth_thread.join(timeout=0.5)
    
    print(f"Done! ({len(color_frames)} frames)")
    
    # Don't save here - let the main loop handle saving to avoid duplicates
    # The save_queue is only used for coordination, not actual saving
    
    return color_frames, depth_frames if depth_frames else None, timestamps

def save_clip(color_frames, depth_frames, timestamps, output_dir, clip_num):
    """Save clip as MP4 video + depth data"""
    os.makedirs(output_dir, exist_ok=True)
    
    if len(color_frames) == 0:
        print("  ✗ No frames to save")
        return
    
    # Get video properties
    height, width = color_frames[0].shape[:2]
    fps = len(color_frames) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 30.0
    
    # Save color video as MP4
    video_filename = os.path.join(output_dir, f"clip_{clip_num:04d}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_filename, fourcc, fps, (width, height))
    
    if out.isOpened():
        for frame in color_frames:
            out.write(frame)
        out.release()
        file_size = os.path.getsize(video_filename) / (1024 * 1024)  # MB
        print(f"  ✓ Saved video: {video_filename} ({file_size:.1f} MB)")
    else:
        print(f"  ✗ Could not create video file")
        video_filename = None
    
    # Save depth data
    if depth_frames and len(depth_frames) > 0 and any(d is not None for d in depth_frames):
        depth_dir = os.path.join(output_dir, 'depth')
        os.makedirs(depth_dir, exist_ok=True)
        
        valid_depth_frames = [d for d in depth_frames if d is not None]
        
        # Save depth frames in multiple formats for easy Python access
        import pickle
        
        for i, depth_data in enumerate(depth_frames):
            if depth_data is None:
                continue
            
            # Convert to uint16 if it's float (mm)
            if depth_data.dtype == np.float32 or depth_data.dtype == np.float64:
                depth_uint16 = depth_data.astype(np.uint16)
            else:
                depth_uint16 = depth_data
            
            # Save as .npy (numpy array - easy to load with np.load)
            npy_path = os.path.join(depth_dir, f"frame_{i:06d}_depth.npy")
            np.save(npy_path, depth_uint16)
            
            # Save as .pkl (pickle - also easy Python access)
            pkl_path = os.path.join(depth_dir, f"frame_{i:06d}_depth.pkl")
            with open(pkl_path, 'wb') as f:
                pickle.dump(depth_uint16, f)
        
        # Save all depth frames in a single Python pickle file for easy loading
        all_depth_pkl = os.path.join(depth_dir, 'all_depth_frames.pkl')
        with open(all_depth_pkl, 'wb') as f:
            pickle.dump(valid_depth_frames, f)
        
        # Also save as a Python script with numpy arrays (for direct Python access)
        py_path = os.path.join(depth_dir, 'depth_data.py')
        with open(py_path, 'w') as f:
            f.write("# Depth data for each frame\n")
            f.write("# Load with: import numpy as np; exec(open('depth_data.py').read())\n")
            f.write("import numpy as np\n\n")
            f.write(f"# Total frames: {len(valid_depth_frames)}\n\n")
            for i, depth_data in enumerate(depth_frames):
                if depth_data is None:
                    continue
                depth_uint16 = depth_data.astype(np.uint16) if depth_data.dtype in [np.float32, np.float64] else depth_data
                # Save as numpy array string representation (compressed)
                f.write(f"# Frame {i}\n")
                f.write(f"frame_{i}_depth = np.load('frame_{i:06d}_depth.npy')  # Shape: {depth_uint16.shape}, dtype: {depth_uint16.dtype}\n\n")
        
        print(f"  ✓ Saved {len(valid_depth_frames)} depth frames to {depth_dir}/")
        print(f"    - Individual: frame_XXXXXX_depth.npy (numpy)")
        print(f"    - Individual: frame_XXXXXX_depth.pkl (pickle)")
        print(f"    - Combined: all_depth_frames.pkl (all frames)")
        print(f"    - Python: depth_data.py (load helper)")
        
        # Calculate depth statistics
        all_valid = np.concatenate([d[d > 0].flatten() for d in valid_depth_frames if d is not None])
        if len(all_valid) > 0:
            depth_stats = {
                'mean_depth': float(np.mean(all_valid)),
                'median_depth': float(np.median(all_valid)),
                'min_depth': float(np.min(all_valid)),
                'max_depth': float(np.max(all_valid)),
                'units': 'mm' if any(d.dtype == np.float32 for d in valid_depth_frames) else 'raw',
            }
        else:
            depth_stats = {'note': 'No valid depth pixels found'}
    else:
        depth_stats = None
        print(f"  ⚠️  No depth data available")
    
    # Save metadata
    metadata = {
        'clip_num': clip_num,
        'frames': len(color_frames),
        'duration': timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0,
        'fps': fps,
        'resolution': {'width': width, 'height': height},
        'has_depth': depth_frames is not None and len(depth_frames) > 0,
        'video_file': os.path.basename(video_filename) if video_filename else None,
        'timestamp': datetime.now().isoformat()
    }
    
    if depth_stats:
        metadata['depth_stats'] = depth_stats
    
    with open(os.path.join(output_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"  ✓ Saved metadata")

def main():
    clip_duration = 3.0  # seconds
    target_fps = 30  # frames per second (will use actual camera max fps)
    
    # Kill any processes that might be using the camera
    print("Checking for processes using camera...")
    import subprocess
    try:
        # Kill processes using video devices
        result = subprocess.run(['fuser', '-k', '/dev/video*'], 
                              capture_output=True, stderr=subprocess.DEVNULL, timeout=2)
        print("  ✓ Released any video devices")
    except:
        pass
    
    try:
        # Kill any Python processes with our script name
        result = subprocess.run(['pkill', '-f', 'capture_video_clip'], 
                              capture_output=True, stderr=subprocess.DEVNULL, timeout=1)
    except:
        pass
    
    time.sleep(0.5)  # Give it a moment for devices to be released
    
    print("=" * 60)
    print("RealSense Video Clip Capture with Depth")
    print("=" * 60)
    print(f"Clip Duration: {clip_duration}s")
    print(f"Target FPS: {target_fps}")
    print("=" * 60)
    
    # Use RealSense SDK for RGB color camera (V4L2 only exposes IR cameras)
    # NOTE: /dev/video4 appears to be RGB color via V4L2 (YUYV format)
    # RealSense SDK often fails with "No device connected" even when device exists
    # This is a known SDK bug - fallback to V4L2 is automatic
    # Set to False to skip SDK and use V4L2 directly (faster, and /dev/video4 is RGB)
    use_realsense = False  # Skip SDK - use V4L2 directly since /dev/video4 is RGB
    if use_realsense:
        print(f"\nAttempting RealSense SDK for RGB color camera (will fallback to V4L2 if it fails)")
    else:
        print(f"\nUsing V4L2 directly with /dev/video4 (RGB color camera)")
        print(f"  Note: Skipping RealSense SDK (known to fail with 'No device connected')")
    
    # Fallback to V4L2 if SDK not available
    color_cap = None
    depth_cap = None
    
    if not use_realsense:
        print("\nTrying V4L2 for color + depth...")
        device = find_camera()
        if device is None:
            print("✗ Could not find camera!")
            return
        
        color_cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not color_cap.isOpened():
            print(f"✗ Could not open {device}")
            return
        
        # Try to set highest resolution and framerate available
        # RealSense /dev/video4 supports up to 1920x1080, but lower resolutions have higher framerates
        # Optimize for highest framerate at highest usable resolution
        resolutions = [
            (1920, 1080),
            (1280, 720),
            (848, 480),
            (640, 480),
            (640, 360),
        ]
        
        # Try highest framerates first (60, 30, 15, etc.)
        target_framerates = [60, 30, 15, 10]
        
        best_config = None
        best_fps = 0
        best_resolution = None
        
        # Find the configuration with the highest framerate
        # Prioritize higher resolution if framerate is the same
        for w, h in resolutions:
            for target_fps_val in target_framerates:
                color_cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                color_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                color_cap.set(cv2.CAP_PROP_FPS, target_fps_val)
                
                # Check what we actually got
                test_w = int(color_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                test_h = int(color_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                test_fps = color_cap.get(cv2.CAP_PROP_FPS)
                
                if test_w == w and test_h == h:
                    # Check if this is better (higher fps, or same fps with higher resolution)
                    is_better = False
                    if test_fps > best_fps:
                        is_better = True
                    elif test_fps == best_fps and best_resolution:
                        # Same fps - prefer higher resolution
                        current_pixels = w * h
                        best_pixels = best_resolution[0] * best_resolution[1]
                        if current_pixels > best_pixels:
                            is_better = True
                    
                    if is_better or best_config is None:
                        best_config = (test_w, test_h, test_fps)
                        best_fps = test_fps
                        best_resolution = (test_w, test_h)
        
        # Apply the best configuration we found
        if best_config:
            actual_width, actual_height, actual_fps = best_config
            color_cap.set(cv2.CAP_PROP_FRAME_WIDTH, actual_width)
            color_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, actual_height)
            color_cap.set(cv2.CAP_PROP_FPS, actual_fps)
        else:
            # If none worked, use default
            actual_width = int(color_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(color_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = color_cap.get(cv2.CAP_PROP_FPS)
        
        print(f"✓ Color stream: {actual_width}x{actual_height} @ {actual_fps:.1f}fps (max)")
        
        # Try to find depth device (exclude the one used for color to avoid conflicts)
        depth_device = find_depth_device(exclude_device=device)
        if depth_device:
            if depth_device == '/dev/video0':
                # /dev/video0 uses Z16 format - OpenCV can't read it directly
                # We'll read it via v4l2-ctl command
                print(f"✓ Depth stream found at {depth_device} (Z16 format - reading via v4l2-ctl)")
                depth_cap = None  # We'll read directly, no OpenCV needed
            else:
                # Use V4L2 backend explicitly for other depth devices
                depth_cap = cv2.VideoCapture(depth_device, cv2.CAP_V4L2)
                if depth_cap.isOpened():
                    print(f"✓ Depth/IR stream found at {depth_device}")
                else:
                    depth_cap = None
        else:
            print("  ⚠️  No depth/IR stream found via V4L2")
    
    # Create output directory with timestamp
    base_dir = ".videos"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = os.path.join(base_dir, timestamp)
    os.makedirs(output_base, exist_ok=True)
    
    print(f"\nOutput directory: {output_base}/")
    print("Press Ctrl+C to stop\n")
    
    # Background thread for saving clips (non-blocking)
    save_queue = Queue(maxsize=2)  # Allow 2 clips queued
    save_thread_running = threading.Event()
    save_thread_running.set()
    
    def save_worker():
        """Background thread to save clips"""
        clip_num = 0
        while save_thread_running.is_set() or not save_queue.empty():
            try:
                # Wait for clip with timeout
                item = save_queue.get(timeout=0.5)
                color_frames, depth_frames, timestamps = item
                clip_num += 1
                
                clip_dir = os.path.join(output_base, f"clip_{clip_num:04d}")
                save_clip(color_frames, depth_frames, timestamps, clip_dir, clip_num)
                print(f"  ✓ Clip #{clip_num} saved (background)")
                save_queue.task_done()
            except:
                pass
    
    save_thread = threading.Thread(target=save_worker, daemon=True)
    save_thread.start()
    
    clip_num = 0
    
    try:
        while True:
            clip_num += 1
            print(f"\n📹 Clip #{clip_num}")
            
            # Capture clip (returns immediately)
            if use_realsense:
                color_frames, depth_frames, timestamps = capture_clip_realsense(clip_duration, target_fps)
                if color_frames is None:
                    print("  ✗ RealSense SDK capture failed - falling back to V4L2")
                    # Fallback to V4L2 if SDK fails
                    use_realsense = False
                    if color_cap is None:
                        print("\nTrying V4L2 for color + depth...")
                        device = find_camera()
                        if device is None:
                            print("✗ Could not find camera!")
                            continue
                        
                        color_cap = cv2.VideoCapture(device)
                        if not color_cap.isOpened():
                            print(f"✗ Could not open {device}")
                            continue
                        
                        width = int(color_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(color_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        actual_fps = color_cap.get(cv2.CAP_PROP_FPS)
                        print(f"✓ Color stream: {width}x{height} @ {actual_fps:.1f}fps")
                        
                        # Try to find depth device (exclude the one used for color to avoid conflicts)
                        depth_device = find_depth_device(exclude_device=device)
                        if depth_device:
                            if depth_device == '/dev/video0':
                                print(f"✓ Depth stream found at {depth_device} (Z16 format - reading via v4l2-ctl)")
                                depth_cap = None
                            else:
                                depth_cap = cv2.VideoCapture(depth_device, cv2.CAP_V4L2)
                                if depth_cap.isOpened():
                                    print(f"✓ Depth/IR stream found at {depth_device}")
                                else:
                                    depth_cap = None
                        else:
                            print("  ⚠️  No depth/IR stream found via V4L2")
                    
                    # Try V4L2 capture
                    actual_fps_int = int(actual_fps) if 'actual_fps' in locals() else 30
                    depth_device_path = depth_device if 'depth_device' in locals() else None
                    color_frames, depth_frames, timestamps = capture_clip_v4l2(
                        color_cap, depth_cap, clip_duration, actual_fps_int, depth_device_path, None
                    )
                    
                    if len(color_frames) == 0:
                        print("  ✗ No frames captured, skipping...")
                        continue
                else:
                    # RealSense SDK worked - continue
                    pass
            else:
                actual_fps_int = int(actual_fps) if 'actual_fps' in locals() else 30
                depth_device_path = depth_device if 'depth_device' in locals() else None
                # Don't pass save_queue to avoid duplicate saves - save here instead
                color_frames, depth_frames, timestamps = capture_clip_v4l2(
                    color_cap, depth_cap, clip_duration, actual_fps_int, depth_device_path, None
                )
            
            if len(color_frames) == 0:
                print("  ✗ No frames captured, skipping...")
                continue
            
            # Queue for background save (non-blocking) - only save once here
            try:
                save_queue.put_nowait((color_frames, depth_frames, timestamps))
                print(f"  ✓ Clip #{clip_num} queued for save (continuing capture...)")
            except:
                print(f"  ⚠️  Save queue full - dropping clip #{clip_num}")
            
            # No delay - continue immediately to next clip!
    
    except KeyboardInterrupt:
        print("\n\nStopping...")
    
    finally:
        # Stop save thread
        save_thread_running.clear()
        save_thread.join(timeout=5.0)
        
        # Wait for any pending saves
        save_queue.join()
        
        if color_cap:
            color_cap.release()
            print(f"✓ Color camera released")
        if depth_cap:
            depth_cap.release()
            print(f"✓ Depth camera released")
        print(f"\n📊 Total clips captured: {clip_num}")
        print(f"📁 Output directory: {output_base}")

if __name__ == '__main__':
    main()

