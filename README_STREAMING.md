# UDP Streaming Setup Guide

## Overview

The producer (Jetson Nano) captures video and streams it over UDP RTP to a consumer (DGX Spark).

## Network Architecture

```
┌─────────────────┐         UDP Stream         ┌─────────────────┐
│  Jetson Nano    │ ──────────────────────────> │   DGX Spark     │
│  (Producer)     │       192.168.x.x:8554     │  (Consumer)     │
│  192.168.x.x    │                             │  100.94.31.62   │
└─────────────────┘                             └─────────────────┘
```

## How to Run

### Step 1: On Jetson Nano (Producer)

**Default mode** - Sends to all interfaces (broadcast):
```bash
./run-producer.sh
```

**Send to specific IP** (DGX Spark IP):
```bash
python3 producer/udp_rtp_producer.py --source deepstream --device /dev/video2 --host 100.94.31.62 --port 8554
```

### Step 2: On DGX Spark (Consumer)

**Using Docker (recommended)**:
```bash
cd consumer
docker-compose up
```

Or set environment variable:
```bash
export RTSP_URL=udp://JETSON_IP:8554
# Then run your consumer
```

**Using Python directly**:
```bash
RTSP_URL=udp://JETSON_IP:8554 python3 consumer/rtsp_consumer.py
```

## Important Notes

1. **UDP is connectionless**: There's no TCP-style "connection"
2. **Producer sends**, **Consumer receives**
3. **Host parameter**: 
   - `0.0.0.0` = sends to all interfaces (broadcast)
   - Specific IP = sends to that IP only
4. **Consumer just listens** on a port - doesn't need to "connect" anywhere

## Testing Commands

### Test if producer is sending (on DGX Spark):
```bash
sudo tcpdump -i any udp port 8554
```

### Test with GStreamer viewer (on DGX Spark):
```bash
gst-launch-1.0 udpsrc port=8554 ! application/x-rtp,encoding-name=H264,payload=96 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false
```

## Troubleshooting

**Problem**: Consumer not receiving frames

**Solution**: Check producer is sending to correct IP
```bash
# On Jetson Nano - check producer output:
# Should show: "Network URL: udp://192.168.x.x:8554"

# To send to DGX Spark explicitly:
python3 producer/udp_rtp_producer.py --source deepstream --host 100.94.31.62
```

**Problem**: "Cannot assign requested address" error

**Solution**: Consumer shouldn't use `address=` parameter in `udpsrc`, just listen on port
```bash
# Correct:
udpsrc port=8554 !

# Wrong:
udpsrc port=8554 address=100.94.31.62 !
```

