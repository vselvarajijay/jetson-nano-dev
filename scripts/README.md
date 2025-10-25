# DeepStream Web Server

A Python web server that captures video from DeepStream pipelines and streams it live via HTTP. This allows you to view your DeepStream video feed in any web browser.

## Features

- 🎥 **Live Video Streaming**: Real-time video feed from DeepStream/GStreamer pipelines
- 🌐 **Web Interface**: Modern, responsive web UI for viewing the stream
- 🔧 **Multiple Sources**: Support for V4L2 cameras and DeepStream pipelines
- 📱 **Mobile Friendly**: Responsive design that works on all devices
- ⚡ **Low Latency**: Optimized for minimal delay
- 🔄 **Auto-reconnect**: Automatic stream recovery on errors

## Prerequisites

### System Dependencies
```bash
# Install GStreamer development packages
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# For DeepStream support (if using DeepStream)
sudo apt-get install -y \
    libnvinfer-dev \
    libnvinfer-plugin-dev \
    libnvparsers-dev \
    libnvonnxparsers-dev \
    libnvinfer-bin
```

### Python Dependencies
```bash
# Install Python packages
pip3 install -r requirements.txt
```

## Usage

### Basic Usage
```bash
# Run with default settings (V4L2 camera on /dev/video4)
python3 deepstream_web_server.py

# Run on different host/port
python3 deepstream_web_server.py --host 192.168.1.100 --port 8080

# Use DeepStream pipeline instead of V4L2
python3 deepstream_web_server.py --source deepstream
```

### Command Line Options
```bash
python3 deepstream_web_server.py [OPTIONS]

Options:
  --host TEXT      Host to bind to (default: 0.0.0.0)
  --port INTEGER   Port to bind to (default: 5000)
  --source TEXT    Video source type: v4l2 or deepstream (default: v4l2)
  --device TEXT    Video device path (default: /dev/video4)
  --help           Show this message and exit
```

### Examples

#### RealSense Camera (V4L2)
```bash
python3 deepstream_web_server.py --source v4l2 --device /dev/video4
```

#### DeepStream Pipeline
```bash
python3 deepstream_web_server.py --source deepstream
```

#### Custom Network Configuration
```bash
python3 deepstream_web_server.py --host 192.168.1.50 --port 8080
```

## Accessing the Stream

1. **Start the server** using one of the commands above
2. **Open your web browser** and navigate to:
   - Local access: `http://localhost:5000`
   - Network access: `http://[YOUR_IP]:5000`
3. **View the live stream** in the web interface

## Web Interface Features

- **Live Video Display**: Real-time video feed with automatic refresh
- **Stream Information**: Display of resolution, frame rate, and technical details
- **Fullscreen Mode**: Click the fullscreen button for immersive viewing
- **Mobile Responsive**: Works on phones, tablets, and desktops
- **Auto-reconnect**: Automatically handles connection issues

## Configuration

### Video Sources

#### V4L2 Source (RealSense/Webcam)
```python
# Default configuration
source_type = "v4l2"
device = "/dev/video4"
resolution = "640x480"
framerate = "30/1"
```

#### DeepStream Source
```python
# DeepStream pipeline configuration
source_type = "deepstream"
# Uses NVIDIA camera or video file
```

### Custom Pipeline Configuration

You can modify the pipeline strings in the `setup_gstreamer_pipeline()` method:

```python
# Custom V4L2 pipeline
pipeline_str = """
v4l2src device=/dev/video0 !
video/x-raw,width=1280,height=720,framerate=30/1 !
videoconvert !
video/x-raw,format=BGR !
appsink emit-signals=true max-buffers=1 drop=true sync=false
"""
```

## Troubleshooting

### Common Issues

1. **Permission Denied on Video Device**
   ```bash
   sudo usermod -a -G video $USER
   # Log out and back in
   ```

2. **GStreamer Pipeline Errors**
   ```bash
   # Test pipeline manually
   gst-launch-1.0 v4l2src device=/dev/video4 ! videoconvert ! autovideosink
   ```

3. **Port Already in Use**
   ```bash
   # Use different port
   python3 deepstream_web_server.py --port 8080
   ```

4. **No Video Device Found**
   ```bash
   # List available video devices
   ls /dev/video*
   
   # Check device capabilities
   v4l2-ctl --list-devices
   ```

### Debug Mode

Enable debug logging by modifying the script:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

### For Better Performance
- Use hardware-accelerated codecs when available
- Adjust frame rate and resolution based on network capacity
- Use wired network connection for lower latency
- Close unnecessary applications to free up resources

### Network Considerations
- **Local Network**: Best performance, lowest latency
- **WiFi**: Good performance with stable connection
- **Internet**: May have higher latency depending on connection

## Security Notes

- The server binds to `0.0.0.0` by default, making it accessible from any network interface
- For production use, consider:
  - Using a reverse proxy (nginx)
  - Implementing authentication
  - Using HTTPS
  - Restricting access to specific IP ranges

## Integration with DeepStream

This web server can be integrated with existing DeepStream applications:

1. **Modify DeepStream Pipeline**: Add an `appsink` element to your DeepStream pipeline
2. **Use DeepStream Output**: Connect the DeepStream output to the web server
3. **Custom Processing**: Add your own video processing between DeepStream and web output

## License

This project is provided as-is for educational and development purposes.
