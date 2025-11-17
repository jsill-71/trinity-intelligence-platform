FROM python:3.11-slim

WORKDIR /app

COPY services/backup-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/backup-service/src/ ./src/

CMD ["python", "src/backup_manager.py"]
