FROM python:3.11-slim

WORKDIR /app

COPY services/scheduler-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/scheduler-service/src/ ./src/

CMD ["python", "src/scheduler.py"]
