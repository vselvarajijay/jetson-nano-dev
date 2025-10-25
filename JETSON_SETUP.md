# Jetson Nano Setup Guide

## Working Configuration

This setup has been tested and verified with the following versions:

| Component | Version |
|-----------|---------|
| **OS** | Ubuntu 22.04 (Jammy) |
| **JetPack** | 6.x |
| **DeepStream SDK** | 7.1.0 |
| **DeepStream App** | 7.1.0 |
| **CUDA Driver** | 12.6 |
| **CUDA Runtime** | 12.6 |
| **TensorRT** | 10.3 |
| **cuDNN** | 9.0 |
| **libNVWrap360** | 2.0.1d3 |

## Installation Steps

### 1. Fresh Installation

To start completely fresh:
1. **Jump pins 9 & 10** on the Jetson Nano (for recovery mode)
2. **Install through NVIDIA SDK Manager** using the versions listed above

### 2. SDK Manager Configuration

From the SDK Manager, ensure you have the following components selected:
- ✅ **DeepStream SDK**
- ✅ **CUDA Toolkit**
- ✅ **TensorRT**
- ✅ **cuDNN**

### 3. Intel RealSense SDK Installation

To install the RealSense SDK from the submodule, build from source:

```bash
cd installRealSenseSDK/scripts
sudo ./buildLibrealsense.sh -v v2.54.2 -j4
```

**Note:** This builds Librealsense version 2.54.2 with 4 parallel jobs for faster compilation.

### 4. Verification

After the build completes, verify the camera is working:

```bash
realsense-viewer
```

You should be able to:
- Select the camera from the device list
- View the camera feed
- Access depth and color streams

## Troubleshooting

If you encounter issues:
- Ensure all dependencies are installed correctly
- Check that the RealSense camera is properly connected
- Verify USB 3.0 connection for optimal performance
