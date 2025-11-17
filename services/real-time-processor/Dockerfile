FROM python:3.11-slim

WORKDIR /app

COPY services/real-time-processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/real-time-processor/src/ ./src/

CMD ["python", "src/processor.py"]
