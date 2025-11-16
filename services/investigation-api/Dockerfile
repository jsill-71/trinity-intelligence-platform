FROM python:3.12-slim

WORKDIR /app

RUN pip install fastapi uvicorn neo4j httpx pydantic pydantic-settings

COPY services/investigation-api/src/ ./services/investigation-api/src/

EXPOSE 8000

CMD ["uvicorn", "services.investigation-api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
