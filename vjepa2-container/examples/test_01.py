import torch
import numpy as np
from torchvision.io import read_video

from transformers import (
    AutoVideoProcessor,
    AutoModelForVideoClassification,
    infer_device
)

device = infer_device()

# Hugging Face JEPA2 Video Classifier
hf_repo = "facebook/vjepa2-vitl-fpc16-256-ssv2"
model = AutoModelForVideoClassification.from_pretrained(hf_repo).to(device)
processor = AutoVideoProcessor.from_pretrained(hf_repo)

# Video URL
video_url = "https://huggingface.co/datasets/nateraw/kinetics-mini/resolve/main/val/bowling/-WH-lxmGJVY_000005_000015.mp4"

# Download + decode with torchvision
# Returns tensor: [T, H, W, C]
video, _, _ = read_video(video_url, pts_unit="sec")

# Convert to float, CHW format
video = video.permute(0, 3, 1, 2).float()  # [T, C, H, W]

# Sample frames according to model needs
total_frames = video.shape[0]
num_frames = model.config.frames_per_clip

indices = torch.linspace(0, total_frames - 1, steps=num_frames).long()
video = video[indices]

# Preprocess
inputs = processor(list(video), return_tensors="pt").to(device)

# Inference
with torch.no_grad():
    outputs = model(**inputs)

logits = outputs.logits
probs = torch.softmax(logits, dim=-1)[0]

# Top-5 results
top5 = torch.topk(probs, 5)

print("Top 5 predicted class names:")
for idx, prob in zip(top5.indices, top5.values):
    label = model.config.id2label[idx.item()]
    print(f" - {label}: {prob.item():.2f}")
