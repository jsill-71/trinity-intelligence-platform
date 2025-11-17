FROM python:3.11-slim

WORKDIR /app

COPY services/rate-limiter/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/rate-limiter/src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
