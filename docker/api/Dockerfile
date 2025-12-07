FROM python:3.11-slim

# Install system dependencies
RUN apt-get update
RUN apt-get install -y curl docker.io
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python requirements
COPY docker/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ .

# Expose API port
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]