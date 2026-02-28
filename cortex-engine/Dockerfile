# Stage 1: Download pre-exported ONNX model (no torch needed)
FROM python:3.11-slim AS model-builder
WORKDIR /build
COPY scripts/download_model.py scripts/
RUN python scripts/download_model.py

# Stage 2: Production image
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=model-builder /build/models/ /app/models/
COPY app/ /app/app/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1
CMD ["sh", "entrypoint.sh"]
