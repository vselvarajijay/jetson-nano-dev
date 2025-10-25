# Jetson Nano Initial Setup Guide

## Fresh Installation

To start completely fresh:
1. Jump pins 9 & 10 on the Jetson Nano
2. Install through NVIDIA SDK Manager

## SDK Manager Configuration

From the SDK Manager, make sure to have **DeepStream** selected.

## Intel RealSense SDK Installation

To install the RealSense SDK from the submodule, build from source:

```bash
cd installRealSenseSDK/scripts
sudo ./buildLibrealsense.sh -v v2.54.2 -j4
```

## Verification

After the build completes, run the RealSense viewer to verify the camera is working:

```bash
realsense-viewer
```

You should be able to select and view the camera feed.
