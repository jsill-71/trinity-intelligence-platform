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
COPY services/kg-projector/ ./services/kg-projector/

# Run projector
CMD ["python", "-m", "services.kg-projector.src.main"]
