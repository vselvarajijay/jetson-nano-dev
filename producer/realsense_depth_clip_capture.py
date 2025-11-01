#!/usr/bin/env python3
"""
RealSense Depth Clip Capture for VJEPA Training (Fixed)
Captures 3-second clips with raw depth data from Intel RealSense camera
Balanced sampling: saves all motion clips + subset of no-motion clips
Resolution: 640x480 @ 15fps

Fixes applied:
- Depth scale conversion to mm
- Frame alignment between depth and color
- Proper frame timing (removed conflicting sleep)
- Camera warmup period
- Clip validation before saving
- Configurable parameters
- Better error handling and tracking
- Depth statistics in metadata
"""

import pyrealsense2 as rs
import numpy as np
import cv2
import json
import os
import sys
import random
from datetime import datetime
import time

class RealSenseDepthClipCapture:
    def __init__(self, 
                 clip_duration=3.0, 
                 fps=15, 
                 width=640, 
                 height=480,
                 motion_threshold=100,
                 motion_pixel_percent=0.01,
                 no_motion_keep_probability=0.25,
                 jpeg_quality=95,
                 colormap=cv2.COLORMAP_INFERNO,
                 random_seed=None,
                 warmup_frames=30,
                 max_frame_misses=5,
                 min_frames_ratio=0.8):
        """
        Initialize RealSense depth clip capture
        
        Args:
            clip_duration: Duration of each clip in seconds (default: 3.0)
            fps: Frames per second (default: 15)
            width: Frame width (default: 640)
            height: Frame height (default: 480)
            motion_threshold: Minimum depth change in mm to consider motion (default: 100)
            motion_pixel_percent: Fraction of pixels that must change (default: 0.01)
            no_motion_keep_probability: Probability to keep no-motion clips (default: 0.25)
            jpeg_quality: JPEG compression quality 0-100 (default: 95)
            colormap: OpenCV colormap for depth visualization (default: COLORMAP_INFERNO)
            random_seed: Random seed for reproducible sampling (default: None)
            warmup_frames: Number of frames to discard during warmup (default: 30)
            max_frame_misses: Max consecutive frame capture errors before skipping clip (default: 5)
            min_frames_ratio: Minimum ratio of captured/expected frames (default: 0.8)
        """
        self.clip_duration = clip_duration
        self.fps = fps
        self.width = width
        self.height = height
        
        # Motion detection parameters
        self.motion_threshold = motion_threshold
        self.motion_pixel_percent = motion_pixel_percent
        
        # VJEPA balanced sampling: keep subset of no-motion clips
        self.no_motion_keep_probability = no_motion_keep_probability
        
        # Quality and visualization parameters
        self.jpeg_quality = jpeg_quality
        self.colormap = colormap
        
        # Reliability parameters
        self.warmup_frames = warmup_frames
        self.max_frame_misses = max_frame_misses
        self.min_frames_ratio = min_frames_ratio
        
        # Set random seed for reproducibility
        if random_seed is not None:
            random.seed(random_seed)
            print(f"Random seed set to: {random_seed}")
        
        # Pipeline configuration
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Configure streams
        self.config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        self.config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        
        # Alignment object (align depth to color)
        self.align = rs.align(rs.stream.color)
        
        # Depth scale (will be set when pipeline starts)
        self.depth_scale = None
        
        # Output directory structure
        self.base_dir = os.getcwd()
        self.extract_dir = None
        
        # Statistics
        self.clip_count = 0
        self.motion_clips_saved = 0
        self.no_motion_clips_saved = 0
        self.no_motion_clips_skipped = 0
        self.clips_validation_failed = 0
        
    def calculate_motion(self, depth_frame_1, depth_frame_2):
        """
        Calculate motion between two depth frames
        
        Args:
            depth_frame_1: Previous depth frame (numpy array, float32, in mm)
            depth_frame_2: Current depth frame (numpy array, float32, in mm)
            
        Returns:
            motion_score: Percentage of pixels with significant change
        """
        # Create mask for valid depth (non-zero values)
        valid_mask = (depth_frame_1 > 0) & (depth_frame_2 > 0)
        
        if np.sum(valid_mask) == 0:
            return 0.0
        
        # Calculate absolute difference
        depth_diff = np.abs(depth_frame_2 - depth_frame_1)
        
        # Count pixels with change above threshold
        motion_mask = (depth_diff > self.motion_threshold) & valid_mask
        motion_pixels = np.sum(motion_mask)
        total_valid_pixels = np.sum(valid_mask)
        
        # Return percentage of pixels with motion
        return motion_pixels / total_valid_pixels if total_valid_pixels > 0 else 0.0
    
    def has_motion(self, frames):
        """
        Check if a sequence of frames has significant motion
        
        Args:
            frames: List of depth frame numpy arrays (float32, in mm)
            
        Returns:
            tuple: (has_motion: bool, motion_score: float)
        """
        if len(frames) < 2:
            return False, 0.0
        
        # Compare consecutive frames
        total_motion = 0.0
        comparisons = 0
        
        for i in range(len(frames) - 1):
            motion_score = self.calculate_motion(frames[i], frames[i + 1])
            total_motion += motion_score
            comparisons += 1
        
        # Average motion across all frame pairs
        avg_motion = total_motion / comparisons if comparisons > 0 else 0.0
        
        # Motion detected if average exceeds threshold
        has_motion_result = avg_motion > self.motion_pixel_percent
        
        return has_motion_result, avg_motion
    
    def should_save_clip(self, has_motion_result, motion_score):
        """
        Determine if clip should be saved based on motion and sampling strategy
        
        Args:
            has_motion_result: Whether motion was detected (bool)
            motion_score: Motion score (float 0-1)
            
        Returns:
            tuple: (should_save: bool, reason: str)
        """
        if has_motion_result:
            # Always save clips with motion
            return True, "motion"
        else:
            # Randomly sample no-motion clips based on probability
            if random.random() < self.no_motion_keep_probability:
                return True, "no_motion_sampled"
            else:
                return False, "no_motion_skipped"
    
    def validate_clip(self, depth_frames, color_frames, expected_frames):
        """
        Validate clip quality before saving
        
        Args:
            depth_frames: List of depth frames
            color_frames: List of color frames
            expected_frames: Expected number of frames
            
        Returns:
            tuple: (is_valid: bool, reason: str)
        """
        # Check frame count
        actual_frames = len(depth_frames)
        if actual_frames < expected_frames * self.min_frames_ratio:
            return False, f"Insufficient frames: {actual_frames}/{expected_frames}"
        
        # Check if frames match
        if len(depth_frames) != len(color_frames):
            return False, "Depth and color frame count mismatch"
        
        # Check for sufficient valid depth data
        valid_depth_ratios = []
        for depth_frame in depth_frames:
            valid_pixels = np.sum(depth_frame > 0)
            total_pixels = depth_frame.size
            valid_ratio = valid_pixels / total_pixels if total_pixels > 0 else 0.0
            valid_depth_ratios.append(valid_ratio)
        
        avg_valid_ratio = np.mean(valid_depth_ratios)
        if avg_valid_ratio < 0.3:  # At least 30% valid depth
            return False, f"Insufficient depth coverage: {avg_valid_ratio:.1%}"
        
        return True, "Valid"
    
    def get_depth_statistics(self, depth_frames):
        """
        Calculate depth statistics for metadata
        
        Args:
            depth_frames: List of depth frames (float32, in mm)
            
        Returns:
            dict: Statistics about depth data
        """
        stats = {
            'mean_depth_mm': [],
            'median_depth_mm': [],
            'valid_pixel_ratio': []
        }
        
        for frame in depth_frames:
            valid_mask = frame > 0
            if np.any(valid_mask):
                stats['mean_depth_mm'].append(float(np.mean(frame[valid_mask])))
                stats['median_depth_mm'].append(float(np.median(frame[valid_mask])))
            else:
                stats['mean_depth_mm'].append(0.0)
                stats['median_depth_mm'].append(0.0)
            
            stats['valid_pixel_ratio'].append(float(np.sum(valid_mask) / frame.size))
        
        # Calculate overall statistics
        return {
            'mean_depth_mm': float(np.mean(stats['mean_depth_mm'])),
            'median_depth_mm': float(np.mean(stats['median_depth_mm'])),
            'mean_valid_pixel_ratio': float(np.mean(stats['valid_pixel_ratio'])),
            'per_frame_mean_depth_mm': stats['mean_depth_mm'],
            'per_frame_valid_ratio': stats['valid_pixel_ratio']
        }
    
    def save_clip(self, depth_frames, color_frames, timestamps, clip_dir, clip_type="motion", 
                  expected_frames=None, motion_score=0.0):
        """
        Save clip data to disk
        
        Args:
            depth_frames: List of depth frame numpy arrays (float32, in mm)
            color_frames: List of color frame numpy arrays (BGR)
            timestamps: List of frame timestamps
            clip_dir: Directory to save clip data
            clip_type: Type of clip ("motion" or "no_motion")
            expected_frames: Expected number of frames
            motion_score: Motion score for this clip
        """
        os.makedirs(clip_dir, exist_ok=True)
        
        depth_dir = os.path.join(clip_dir, 'depth')
        color_dir = os.path.join(clip_dir, 'color')
        os.makedirs(depth_dir, exist_ok=True)
        os.makedirs(color_dir, exist_ok=True)
        
        # Save frames
        for i, (depth_frame, color_frame, timestamp) in enumerate(zip(depth_frames, color_frames, timestamps)):
            frame_filename = f"frame_{i:06d}"
            
            # Convert depth back to uint16 for storage (already in mm)
            depth_uint16 = depth_frame.astype(np.uint16)
            
            # Save raw depth as .npy (uint16, units in mm)
            depth_path = os.path.join(depth_dir, f"{frame_filename}_raw.npy")
            np.save(depth_path, depth_uint16)
            
            # Save depth visualization as PNG (colormap)
            depth_vis = self.visualize_depth(depth_uint16)
            depth_vis_path = os.path.join(depth_dir, f"{frame_filename}.png")
            cv2.imwrite(depth_vis_path, depth_vis)
            
            # Save color frame
            color_path = os.path.join(color_dir, f"{frame_filename}.jpg")
            cv2.imwrite(color_path, color_frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        
        # Calculate depth statistics
        depth_stats = self.get_depth_statistics(depth_frames)
        
        # Calculate actual duration
        actual_duration = len(depth_frames) / self.fps
        
        # Save metadata
        metadata = {
            'capture_info': {
                'total_frames': len(depth_frames),
                'expected_frames': expected_frames if expected_frames else len(depth_frames),
                'fps': self.fps,
                'resolution': {'width': self.width, 'height': self.height},
                'clip_duration_seconds': self.clip_duration,
                'actual_duration_seconds': actual_duration,
                'timestamp': datetime.now().isoformat()
            },
            'depth_info': {
                'depth_units_mm': 1.0,
                'depth_scale': self.depth_scale,
                'statistics': depth_stats
            },
            'classification': {
                'clip_type': clip_type,
                'motion_score': motion_score,
                'motion_threshold': self.motion_threshold,
                'motion_pixel_percent': self.motion_pixel_percent
            },
            'timestamps': timestamps
        }
        
        metadata_path = os.path.join(clip_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Print with clip type indicator
        type_emoji = "🎬" if clip_type == "motion" else "📸"
        print(f"{type_emoji} Saved clip: {len(depth_frames)} frames ({clip_type})")
    
    def visualize_depth(self, depth_frame):
        """
        Create visualization of depth frame using colormap
        
        Args:
            depth_frame: Depth frame numpy array (uint16)
            
        Returns:
            BGR image for visualization
        """
        # Apply colormap
        depth_vis = depth_frame.copy()
        
        # Normalize to 0-255 range, filtering zeros
        depth_mask = depth_vis > 0
        if np.any(depth_mask):
            depth_min = np.min(depth_vis[depth_mask])
            depth_max = np.max(depth_vis[depth_mask])
            
            if depth_max > depth_min:
                depth_normalized = np.zeros_like(depth_vis, dtype=np.uint8)
                depth_normalized[depth_mask] = ((depth_vis[depth_mask] - depth_min) / 
                                                (depth_max - depth_min) * 255).astype(np.uint8)
            else:
                depth_normalized = np.zeros_like(depth_vis, dtype=np.uint8)
        else:
            depth_normalized = np.zeros_like(depth_vis, dtype=np.uint8)
        
        # Apply colormap
        depth_colormap = cv2.applyColorMap(depth_normalized, self.colormap)
        
        return depth_colormap
    
    def warmup_camera(self):
        """
        Warm up camera by capturing and discarding initial frames
        This allows auto-exposure and other settings to stabilize
        """
        print(f"Warming up camera ({self.warmup_frames} frames)...", end=' ', flush=True)
        for i in range(self.warmup_frames):
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                if i % 10 == 0 and i > 0:
                    print(f"{i}/{self.warmup_frames}", end=' ', flush=True)
            except RuntimeError:
                print(f"\n⚠️  Warmup frame {i} timeout")
                continue
        print("Done ✓")
    
    def start_streaming(self):
        """Start the RealSense pipeline"""
        print("=" * 60)
        print("RealSense Depth Clip Capture (VJEPA Training)")
        print("=" * 60)
        print(f"Resolution: {self.width}x{self.height} @ {self.fps}fps")
        print(f"Clip Duration: {self.clip_duration}s")
        print(f"Motion Threshold: {self.motion_threshold}mm ({self.motion_pixel_percent*100:.1f}% pixels)")
        print(f"No-Motion Sampling: {self.no_motion_keep_probability*100:.1f}% kept")
        print(f"Min Frames Ratio: {self.min_frames_ratio*100:.0f}%")
        print("=" * 60)
        
        # Start pipeline
        print("Starting RealSense pipeline...")
        try:
            profile = self.pipeline.start(self.config)
            print("✓ Pipeline started")
            
            # Get depth sensor and scale
            depth_sensor = profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            print(f"✓ Depth scale: {self.depth_scale:.6f} (units to meters)")
            print(f"✓ Depth scale: {self.depth_scale * 1000:.3f} mm per unit")
            
        except Exception as e:
            print(f"✗ Failed to start pipeline: {e}")
            sys.exit(1)
        
        # Warmup camera
        self.warmup_camera()
        
        # Create extract directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.extract_dir = os.path.join(self.base_dir, f"{timestamp}_extract")
        os.makedirs(self.extract_dir, exist_ok=True)
        print(f"✓ Output directory: {self.extract_dir}")
        print("=" * 60)
    
    def capture_continuous(self):
        """
        Continuously capture clips with balanced sampling
        """
        try:
            while True:
                self.clip_count += 1
                clip_start_time = time.time()
                
                print(f"\n📹 Capturing clip #{self.clip_count}...", end=' ', flush=True)
                
                # Collect frames for clip duration
                depth_frames = []  # Will store as float32 in mm
                color_frames = []
                timestamps = []
                
                expected_frames = int(self.clip_duration * self.fps)
                
                frames_received = 0
                frame_misses = 0
                
                while frames_received < expected_frames:
                    # Wait for frames
                    try:
                        # Get frames with timeout
                        frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                        
                        # Align depth to color
                        aligned_frames = self.align.process(frames)
                        
                        depth_frame = aligned_frames.get_depth_frame()
                        color_frame = aligned_frames.get_color_frame()
                        
                        if not depth_frame or not color_frame:
                            frame_misses += 1
                            if frame_misses > self.max_frame_misses:
                                print(f"\n⚠️  Too many frame misses ({frame_misses}), skipping clip")
                                break
                            continue
                        
                        # Reset miss counter on successful frame
                        frame_misses = 0
                        
                        # Convert to numpy arrays
                        depth_image = np.asanyarray(depth_frame.get_data())
                        color_image = np.asanyarray(color_frame.get_data())
                        
                        # Convert depth to millimeters (apply depth scale)
                        depth_image_mm = (depth_image.astype(np.float32) * self.depth_scale * 1000.0)
                        
                        # Store frames
                        depth_frames.append(depth_image_mm)
                        color_frames.append(color_image)
                        timestamps.append(time.time())
                        frames_received += 1
                        
                        # Progress indicator
                        if frames_received % 10 == 0:
                            progress = (frames_received / expected_frames) * 100
                            print(f"{progress:.0f}%", end=' ', flush=True)
                        
                    except RuntimeError as e:
                        # Frame capture timeout or error
                        frame_misses += 1
                        if frame_misses > self.max_frame_misses:
                            print(f"\n⚠️  Too many frame errors ({frame_misses}): {e}")
                            break
                        continue
                
                print()  # New line after progress
                
                # Check if we got enough frames
                if frame_misses > self.max_frame_misses or frames_received < expected_frames * self.min_frames_ratio:
                    print(f"✗ Clip #{self.clip_count} failed validation: insufficient frames ({frames_received}/{expected_frames})")
                    self.clips_validation_failed += 1
                    continue
                
                # Validate clip quality
                is_valid, validation_reason = self.validate_clip(depth_frames, color_frames, expected_frames)
                if not is_valid:
                    print(f"✗ Clip #{self.clip_count} failed validation: {validation_reason}")
                    self.clips_validation_failed += 1
                    continue
                
                # Check for motion
                has_motion_result, motion_score = self.has_motion(depth_frames)
                
                # Determine if should save
                should_save, reason = self.should_save_clip(has_motion_result, motion_score)
                
                if should_save:
                    # Save clip
                    clip_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include ms
                    clip_dir = os.path.join(self.extract_dir, f"{clip_timestamp}_clip")
                    
                    clip_type = "motion" if reason == "motion" else "no_motion"
                    try:
                        self.save_clip(depth_frames, color_frames, timestamps, clip_dir, 
                                     clip_type, expected_frames, motion_score)
                        
                        if reason == "motion":
                            self.motion_clips_saved += 1
                            print(f"✓ Clip #{self.clip_count} saved (motion detected, score: {motion_score:.4f})")
                        else:
                            self.no_motion_clips_saved += 1
                            print(f"✓ Clip #{self.clip_count} saved (no-motion sampled, score: {motion_score:.4f})")
                    except Exception as e:
                        print(f"✗ Failed to save clip: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                else:
                    # Skip clip
                    self.no_motion_clips_skipped += 1
                    print(f"✗ Clip #{self.clip_count} skipped (no motion, score: {motion_score:.4f})")
                
                # Stats
                total_saved = self.motion_clips_saved + self.no_motion_clips_saved
                print(f"📊 Total: {self.clip_count} | Saved: {total_saved} "
                      f"(🎬{self.motion_clips_saved} 📸{self.no_motion_clips_saved}) | "
                      f"Skipped: {self.no_motion_clips_skipped} | Failed: {self.clips_validation_failed}")
                
        except KeyboardInterrupt:
            print("\n\nStopping capture...")
            self.print_final_stats()
        finally:
            self.pipeline.stop()
            print("Pipeline stopped")
    
    def print_final_stats(self):
        """Print final statistics"""
        print("=" * 60)
        print(f"Final Stats:")
        print(f"  Total clips captured: {self.clip_count}")
        print(f"  Clips saved: {self.motion_clips_saved + self.no_motion_clips_saved}")
        print(f"    - Motion clips: {self.motion_clips_saved}")
        print(f"    - No-motion clips: {self.no_motion_clips_saved}")
        print(f"  Clips skipped (no motion): {self.no_motion_clips_skipped}")
        print(f"  Clips failed validation: {self.clips_validation_failed}")
        print(f"  Output directory: {self.extract_dir}")
        print("=" * 60)
    
    def run(self):
        """Run the capture system"""
        self.start_streaming()
        self.capture_continuous()


def main():
    """Main entry point"""
    capture = RealSenseDepthClipCapture(
        clip_duration=3.0,
        fps=15,
        width=640,
        height=480,
        motion_threshold=100,  # mm
        motion_pixel_percent=0.01,  # 1% of pixels
        no_motion_keep_probability=0.25,  # Keep 25% of no-motion clips
        random_seed=42,  # For reproducible sampling
        warmup_frames=30,  # ~2 seconds warmup
        max_frame_misses=5,
        min_frames_ratio=0.8  # Allow up to 20% frame loss
    )
    
    capture.run()


if __name__ == '__main__':
    sys.exit(main())