FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks (lightweight, no compiler packages needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pre-built wheels from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Render dynamically injects $PORT (default to 8000 for local runs)
ENV PORT=8000
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
