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
    """Find working camera device"""
    for device in ['/dev/video4', '/dev/video0', '/dev/video2']:
        try:
            cap = cv2.VideoCapture(device)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✓ Found camera at {device}")
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
    max_retries = 1 if quick_test else 3
    retry = 0
    while len(devices) == 0 and retry < max_retries:
        time.sleep(0.3 if quick_test else 1.0)
        devices = ctx.query_devices()
        retry += 1
    
    if len(devices) == 0:
        return None, None, None
    
    # Create pipeline with context
    try:
        pipeline = rs.pipeline(ctx)
    except:
        pipeline = rs.pipeline()
    
    config = rs.config()
    
    # Try multiple initialization methods
    profile = None
    max_attempts = 1 if quick_test else 3  # Only try once for quick test
    
    for attempt in range(max_attempts):
        try:
            # Stop any previous attempt
            try:
                pipeline.stop()
                time.sleep(0.1 if quick_test else 0.3)
            except:
                pass
            
            # Try different configs
            if attempt == 0:
                # Standard config
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, fps)
                config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, fps)
            elif attempt == 1:
                # Simpler config
                config.enable_stream(rs.stream.depth)
                config.enable_stream(rs.stream.color)
            else:
                # Fallback: enable all streams
                config = rs.config()
                config.enable_all_streams()
            
            # Start pipeline
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
                time.sleep(0.2)  # Faster retry
            else:
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

def find_depth_device():
    """Try to find a V4L2 device that provides depth/IR data"""
    # RealSense typically exposes depth on /dev/video0 with Z16 format (16-bit depth)
    # Check if /dev/video0 exists and has Z16 format
    import os
    if os.path.exists('/dev/video0'):
        # Try to read a test frame to verify it's depth
        test_frame = read_z16_depth_frame('/dev/video0')
        if test_frame is not None:
            print(f"  ✓ Found depth stream at /dev/video0 (Z16 format, {test_frame.shape})")
            return '/dev/video0'
    
    # Fallback: try other devices
    for device in ['/dev/video2', '/dev/video1']:
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
    
    # If save_queue provided, pass to background save thread (non-blocking)
    if save_queue is not None:
        try:
            save_queue.put_nowait((color_frames, depth_frames, timestamps))
        except:
            print("  ⚠️  Save queue full - dropping clip")
    
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
    target_fps = 15  # frames per second
    
    print("=" * 60)
    print("RealSense Video Clip Capture with Depth")
    print("=" * 60)
    print(f"Clip Duration: {clip_duration}s")
    print(f"Target FPS: {target_fps}")
    print("=" * 60)
    
    # Skip RealSense SDK - it's unreliable. Use V4L2 which we know works!
    # RealSense SDK often fails with "No device connected" even though device exists
    # V4L2 directly accesses /dev/video0 for depth and /dev/video4 for color - much more reliable
    use_realsense = False
    print("\nUsing V4L2 for reliable capture (bypasses RealSense SDK issues)")
    
    # Fallback to V4L2 if needed
    color_cap = None
    depth_cap = None
    
    if not use_realsense:
        print("\nTrying V4L2 for color + depth...")
        device = find_camera()
        if device is None:
            print("✗ Could not find camera!")
            return
        
        color_cap = cv2.VideoCapture(device)
        if not color_cap.isOpened():
            print(f"✗ Could not open {device}")
            return
        
        width = int(color_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(color_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = color_cap.get(cv2.CAP_PROP_FPS)
        
        print(f"✓ Color stream: {width}x{height} @ {actual_fps:.1f}fps")
        
        # Try to find depth device
        depth_device = find_depth_device()
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
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = f"{timestamp}_clips"
    os.makedirs(output_base, exist_ok=True)
    
    print(f"\nOutput directory: {output_base}")
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
                    print("  ✗ Capture failed")
                    continue
            else:
                actual_fps_int = int(actual_fps) if 'actual_fps' in locals() else 30
                depth_device_path = depth_device if 'depth_device' in locals() else None
                color_frames, depth_frames, timestamps = capture_clip_v4l2(
                    color_cap, depth_cap, clip_duration, actual_fps_int, depth_device_path, save_queue
                )
            
            if len(color_frames) == 0:
                print("  ✗ No frames captured, skipping...")
                continue
            
            # Queue for background save (non-blocking)
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

