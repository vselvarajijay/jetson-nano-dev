# RTSP Consumer Docker Deployment for DGX Spark

This directory contains Docker configuration files for deploying the RTSP Consumer on NVIDIA DGX Spark systems.

## 🚀 Quick Start

### Prerequisites

- NVIDIA DGX Spark with Docker and NVIDIA Container Toolkit installed
- Docker Compose v2.0+
- Network access to RTSP stream source

### Basic Deployment

1. **Clone and navigate to the project directory:**
   ```bash
   cd /path/to/jetson-nano-dev
   ```

2. **Build and run the container:**
   ```bash
   # Build the image
   docker-compose build rtsp-consumer
   
   # Run the consumer
   docker-compose up rtsp-consumer
   ```

3. **Run with custom RTSP URL:**
   ```bash
   docker-compose run --rm rtsp-consumer python3 rtsp_consumer.py --url rtsp://your-stream-server:8554/stream
   ```

## 📋 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GST_DEBUG` | `2` | GStreamer debug level (0-6) |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |
| `NVIDIA_VISIBLE_DEVICES` | `all` | GPU devices to expose |

### Volume Mounts

- `./output:/app/output` - Frame output directory
- `./logs:/app/logs` - Log files directory
- `./config:/app/config:ro` - Configuration files (read-only)

### Ports

- `8080:8080` - Web interface port (if implemented)

## 🔧 Advanced Usage

### Custom RTSP URL

```bash
# Override the default RTSP URL
docker-compose run --rm rtsp-consumer python3 rtsp_consumer.py --url rtsp://192.168.1.100:8554/camera1
```

### Resource Limits

The container is configured with resource limits suitable for DGX Spark:

- **Memory**: 8GB limit, 2GB reservation
- **CPU**: 4 cores limit, 1 core reservation
- **GPU**: Full NVIDIA GPU access

### Debugging

```bash
# Run with debug logging
docker-compose run --rm -e GST_DEBUG=4 rtsp-consumer

# Interactive shell for debugging
docker-compose run --rm --entrypoint /bin/bash rtsp-consumer
```

## 🏗️ Building from Source

### Manual Build

```bash
# Build the Docker image
docker build -t rtsp-consumer-dgx .

# Run the container
docker run --rm --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  rtsp-consumer-dgx \
  python3 rtsp_consumer.py --url rtsp://your-stream:8554/test
```

### Multi-stage Build (Optional)

For production deployments, consider using multi-stage builds to reduce image size:

```dockerfile
# Add to Dockerfile for smaller production image
FROM nvidia/cuda:12.2-runtime-ubuntu22.04 as runtime
# ... copy built artifacts from build stage
```

## 🔍 Monitoring and Logs

### View Logs

```bash
# Follow container logs
docker-compose logs -f rtsp-consumer

# View specific log files
docker-compose exec rtsp-consumer tail -f /app/logs/consumer.log
```

### Health Checks

The container includes health checks that verify:
- GStreamer initialization
- Python environment
- Basic functionality

```bash
# Check container health
docker-compose ps
```

## 🧪 Testing

### Test with Local Producer

```bash
# Start both producer and consumer for testing
docker-compose --profile testing up
```

### Network Testing

```bash
# Test RTSP connectivity
docker-compose run --rm rtsp-consumer \
  python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
result = s.connect_ex(('your-rtsp-host', 8554))
print('Connected' if result == 0 else 'Failed')
s.close()
"
```

## 🚨 Troubleshooting

### Common Issues

1. **GStreamer Plugin Errors**
   ```bash
   # Check available plugins
   docker-compose exec rtsp-consumer gst-inspect-1.0 --print-all
   ```

2. **CUDA/GPU Issues**
   ```bash
   # Verify GPU access
   docker-compose exec rtsp-consumer nvidia-smi
   ```

3. **Network Connectivity**
   ```bash
   # Test network from container
   docker-compose exec rtsp-consumer ping your-rtsp-host
   ```

4. **Permission Issues**
   ```bash
   # Fix output directory permissions
   sudo chown -R $USER:$USER ./output ./logs
   ```

### Debug Mode

```bash
# Run with maximum debug output
docker-compose run --rm \
  -e GST_DEBUG=6 \
  -e PYTHONUNBUFFERED=1 \
  rtsp-consumer
```

## 📊 Performance Tuning

### For DGX Spark Optimization

1. **GPU Memory Management**
   ```bash
   # Limit GPU memory usage
   docker run --rm --runtime=nvidia \
     -e NVIDIA_VISIBLE_DEVICES=0 \
     -e CUDA_VISIBLE_DEVICES=0 \
     rtsp-consumer-dgx
   ```

2. **CPU Affinity**
   ```bash
   # Pin to specific CPU cores
   docker run --rm --cpuset-cpus="0-3" rtsp-consumer-dgx
   ```

3. **Memory Optimization**
   ```bash
   # Limit container memory
   docker run --rm -m 4g rtsp-consumer-dgx
   ```

## 🔒 Security Considerations

- Container runs as non-root user
- No privileged mode required for consumer
- Network access limited to necessary ports
- Volume mounts are read-only where possible

## 📈 Scaling

For high-throughput scenarios:

```bash
# Run multiple consumer instances
docker-compose up --scale rtsp-consumer=3
```

## 🆘 Support

For issues specific to DGX Spark deployment:

1. Check NVIDIA Container Toolkit installation
2. Verify GPU driver compatibility
3. Review GStreamer plugin availability
4. Test network connectivity to RTSP source

---

**Note**: This container is optimized for NVIDIA DGX Spark systems. For other platforms, you may need to adjust the base image and dependencies accordingly.
