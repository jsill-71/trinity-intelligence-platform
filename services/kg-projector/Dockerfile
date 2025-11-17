FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    neo4j==5.16.0 \
    nats-py==2.6.0

# Copy service code
COPY services/kg-projector/src/ ./services/kg-projector/src/

CMD ["python", "-m", "services.kg-projector.src.main"]
