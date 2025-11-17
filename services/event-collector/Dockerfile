FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0 \
    nats-py==2.6.0 \
    asyncpg==0.29.0

# Copy shared code
COPY shared/ ./shared/

# Copy service code
COPY services/event-collector/src/ ./services/event-collector/src/

EXPOSE 8000

CMD ["uvicorn", "services.event-collector.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
