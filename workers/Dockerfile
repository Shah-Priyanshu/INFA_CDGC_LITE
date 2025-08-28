FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/workers
ENV PYTHONPATH=/app
CMD ["celery", "-A", "workers.app", "worker", "-l", "info"]
