FROM python:3.11-slim

# g++ нужен Brian2, чтобы компилировать модель через Cython (в ~10 раз быстрее numpy)
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flybrain ./flybrain

ENV FLY_DATA_DIR=/data \
    PYTHONUNBUFFERED=1
CMD ["python", "-m", "flybrain", "run"]
