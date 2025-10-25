# RTSP Consumer Docker Container for DGX Spark
# Optimized for NVIDIA DGX systems with CUDA support

FROM nvidia/cuda:12.2.2-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV GST_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gstreamer-1.0
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core system packages
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    wget \
    curl \
    git \
    # GStreamer core packages
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    # Python GStreamer bindings
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    # OpenCV dependencies
    libopencv-dev \
    python3-opencv \
    # Essential multimedia libraries
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libx264-dev \
    # Network and system libraries
    libssl-dev \
    libglib2.0-dev \
    libgirepository1.0-dev \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements-docker.txt /tmp/requirements-docker.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-docker.txt

# Create application directory
WORKDIR /app

# Copy application files
COPY scripts/rtsp_consumer.py /app/
COPY scripts/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Create directories for output
RUN mkdir -p /app/output /app/logs

# Set up GStreamer environment
RUN echo 'export GST_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gstreamer-1.0' >> /etc/environment
RUN echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> /etc/environment

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print('GStreamer OK')" || exit 1

# Expose port (if needed for web interface)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python3", "rtsp_consumer.py", "--url", "rtsp://host.docker.internal:8554/test"]