# VJEPA2 Inference Service

FastAPI-based HTTP service for video classification inference using Facebook's VJEPA2 model.

## Overview

This service receives video clips (16 frames) from the DeepStream consumer and returns top-k predictions with confidence scores.

## Architecture

```
DeepStream Consumer
    ↓ (batches 16 frames)
HTTP POST /api/v1/infer
    ↓ (JSON with base64-encoded frames)
VJEPA2 Service
    ↓ (inference)
Returns predictions (JSON)
```

## Usage

### Build and Run Service

```bash
cd vjepa2-service
docker-compose build
docker-compose up -d
```

The service will be available at `http://localhost:8000`

### Check Health

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

## API Endpoints

### POST /api/v1/infer

Run inference on a video clip.

**Request:**
```json
{
  "frames": ["base64_encoded_frame1", "base64_encoded_frame2", ...],
  "width": 240,
  "height": 240,
  "format": "BGR"
}
```

**Response:**
```json
{
  "predictions": [
    {"label": "bowling", "confidence": 0.95},
    {"label": "tennis", "confidence": 0.03},
    ...
  ],
  "clip_id": "uuid-here"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/v1/infer \
  -H "Content-Type: application/json" \
  -d '{
    "frames": [...],
    "width": 240,
    "height": 240,
    "format": "BGR"
  }'
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

### GET /

Service information and available endpoints.

## Integration with Consumer

The DeepStream consumer (`consumer/rtsp_consumer.py`) automatically integrates with this service:

1. Consumer receives frames from UDP stream
2. Consumer buffers frames until 16 frames are collected
3. Consumer sends batch to this service via HTTP POST
4. Service returns predictions
5. Consumer logs top prediction

**Configuration:**

Set `VJEPA_SERVICE_URL` environment variable (default: `http://localhost:8000`)

```bash
export VJEPA_SERVICE_URL=http://localhost:8000
```

Or in `consumer/docker-compose.yml`:
```yaml
environment:
  - VJEPA_SERVICE_URL=http://localhost:8000
```

## Model

- **Model**: `facebook/vjepa2-vitl-fpc16-256-ssv2`
- **Frames per clip**: 16
- **Input format**: RGB frames [T, C, H, W]
- **Output**: Top-5 predictions with confidence scores

## Docker Configuration

- **Base image**: `nvcr.io/nvidia/pytorch:25.10-py3`
- **Port**: 8000
- **GPU**: NVIDIA runtime required
- **Shared memory**: 16GB

## Development

### Local Development

```bash
# Build
docker-compose build

# Run
docker-compose up

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### API Documentation

Once the service is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Notes

- The service loads the model on startup (may take a few minutes)
- Model inference requires GPU (NVIDIA)
- Service handles errors gracefully and returns appropriate HTTP status codes
- Consumer sends requests asynchronously to avoid blocking the DeepStream pipeline

