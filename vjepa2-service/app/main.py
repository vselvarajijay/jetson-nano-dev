import base64
import uuid
import numpy as np
import cv2
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.models import InferenceRequest, PredictionResponse, HealthResponse, Prediction
from app.inference import VJEPAInferenceEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VJEPA2 Inference Service",
    description="Video classification inference service using Facebook VJEPA2 model",
    version="1.0.0"
)

# Global inference engine
engine = None


@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    global engine
    try:
        engine = VJEPAInferenceEngine()
        engine.load_model()
        logger.info("Service started successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down service")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        model_loaded=engine is not None and engine.model_loaded
    )


@app.post("/api/v1/infer", response_model=PredictionResponse)
async def infer(request: InferenceRequest):
    """
    Run inference on a video clip
    
    Args:
        request: InferenceRequest with base64-encoded frames
        
    Returns:
        PredictionResponse with top-k predictions
    """
    if engine is None or not engine.model_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service may be starting up."
        )
    
    try:
        # Decode frames from base64
        frames = []
        for i, frame_b64 in enumerate(request.frames):
            try:
                # Decode base64 to bytes
                frame_bytes = base64.b64decode(frame_b64)
                
                # Decode JPEG bytes to numpy array
                frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                
                if frame is None:
                    raise ValueError(f"Failed to decode frame {i}")
                
                # Resize if needed
                if frame.shape[:2] != (request.height, request.width):
                    frame = cv2.resize(frame, (request.width, request.height))
                
                frames.append(frame)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to decode frame {i}: {str(e)}"
                )
        
        # Run inference
        predictions_dict = engine.predict(frames, top_k=5)
        
        # Convert dictionaries to Prediction objects
        predictions = [Prediction(**pred) for pred in predictions_dict]
        
        # Generate clip ID
        clip_id = str(uuid.uuid4())
        
        return PredictionResponse(
            predictions=predictions,
            clip_id=clip_id
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "VJEPA2 Inference Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "infer": "/api/v1/infer"
        },
        "docs": "/docs"
    }

