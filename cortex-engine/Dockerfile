FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements-prod.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh
ENV PYTHONUNBUFFERED=1
CMD ["python", "-c", "import os, sys; sys.stdout.reconfigure(line_buffering=True); port=int(os.environ.get('PORT','8000')); print(f'Starting CortexOS on port {port}', flush=True); import uvicorn; uvicorn.run('cortex.api.app:app', host='0.0.0.0', port=port, log_level='info')"]
