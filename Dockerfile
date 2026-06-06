# dockercraft manager (FastAPI)
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY api ./api
RUN pip install --no-cache-dir .

# The manager talks to the host docker socket (mounted via compose) and
# provisions instance data under /app/data (bind-mounted; see compose.yml).
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
