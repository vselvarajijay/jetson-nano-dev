from pydantic import BaseModel
from typing import List, Dict, Optional


class InferenceRequest(BaseModel):
    """Request model for video inference"""
    frames: List[str]  # Base64 encoded frames (JPEG)
    width: int = 240
    height: int = 240
    format: str = "BGR"


class Prediction(BaseModel):
    """Single prediction result"""
    label: str
    confidence: float


class PredictionResponse(BaseModel):
    """Response model for inference results"""
    predictions: List[Dict[str, float]]  # List of {"label": str, "confidence": float}
    clip_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool

