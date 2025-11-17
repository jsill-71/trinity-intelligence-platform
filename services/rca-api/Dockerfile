FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn neo4j pydantic httpx

COPY services/rca-api/src/ ./services/rca-api/src/

EXPOSE 8000

CMD ["uvicorn", "services.rca-api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
