FROM python:3.11-slim

WORKDIR /app

COPY services/audit-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/audit-service/src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
