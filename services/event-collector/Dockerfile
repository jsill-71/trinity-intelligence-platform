FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock* ./
COPY shared/ ./shared/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Copy service code
COPY services/event-collector/ ./services/event-collector/

# Expose port
EXPOSE 8000

# Run service
CMD ["uvicorn", "services.event-collector.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
