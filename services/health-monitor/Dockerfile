FROM python:3.11-slim

WORKDIR /app

COPY services/health-monitor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/health-monitor/src/ ./src/

CMD ["python", "src/monitor.py"]
