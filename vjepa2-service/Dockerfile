FROM nvcr.io/nvidia/pytorch:25.10-py3

# Workdir
WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# System deps (FFMPEG is needed for video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git curl wget vim build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy deps list
COPY requirements.txt /tmp/requirements.txt

# Python deps (upgrade pip first)
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /tmp/requirements.txt

# ✅ CLEAN TorchAO + reinstall stable PyPI version
RUN pip uninstall -y torchao || true && \
    pip install --no-cache-dir torchao

# ⚠️ NEW — ensure transformers sees torchao properly
# (fixes the "AutoVideoProcessor not found" error)
RUN python - <<'EOF'
import transformers, torchao
print("Transformers:", transformers.__version__)
print("TorchAO:", torchao.__version__)
EOF

# Copy app code
COPY app /workspace/app

# Run FastAPI service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

