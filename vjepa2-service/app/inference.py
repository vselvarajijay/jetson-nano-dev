import torch
import numpy as np
import cv2
from typing import List, Dict
from transformers import (
    AutoVideoProcessor,
    AutoModelForVideoClassification,
    infer_device
)


class VJEPAInferenceEngine:
    """VJEPA2 model inference engine"""
    
    def __init__(self):
        self.device = None
        self.model = None
        self.processor = None
        self.hf_repo = "facebook/vjepa2-vitl-fpc16-256-ssv2"
        self.model_loaded = False
    
    def load_model(self):
        """Load model and processor"""
        if self.model_loaded:
            return
        
        print("Loading VJEPA2 model...")
        self.device = infer_device()
        print(f"Using device: {self.device}")
        
        self.model = AutoModelForVideoClassification.from_pretrained(
            self.hf_repo
        ).to(self.device)
        self.processor = AutoVideoProcessor.from_pretrained(self.hf_repo)
        self.model.eval()
        self.model_loaded = True
        print("Model loaded successfully")
    
    def predict(self, frames: List[np.ndarray], top_k: int = 5) -> List[Dict[str, float]]:
        """
        Predict from list of frames (BGR format)
        
        Args:
            frames: List of numpy arrays [H, W, 3] in BGR format
            top_k: Number of top predictions to return
        
        Returns:
            List of dicts with 'label' and 'confidence' keys
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        # Validate frame count
        expected_frames = self.model.config.frames_per_clip
        if len(frames) != expected_frames:
            raise ValueError(
                f"Expected {expected_frames} frames, got {len(frames)}"
            )
        
        # Convert BGR to RGB
        frames_rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames]
        
        # Convert to torch tensors [T, C, H, W]
        # Each frame is [H, W, 3] RGB, convert to [C, H, W]
        video_tensor = torch.stack([
            torch.from_numpy(f).permute(2, 0, 1).float() 
            for f in frames_rgb
        ])  # [T, C, H, W]
        
        # Preprocess using AutoVideoProcessor
        # Processor expects list of [C, H, W] tensors
        inputs = self.processor(list(video_tensor), return_tensors="pt").to(self.device)
        
        # Inference
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        
        # Top-k results
        top_k_vals, top_k_indices = torch.topk(probs, top_k)
        
        predictions = []
        for idx, prob in zip(top_k_indices, top_k_vals):
            label = self.model.config.id2label[idx.item()]
            predictions.append({
                "label": label,
                "confidence": float(prob.item())
            })
        
        return predictions

