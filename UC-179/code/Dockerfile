# Codificando.AI - UC-179
# Imagen del API Flask del sistema autónomo de reentrenamiento continuo.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    APP_PORT=8003

EXPOSE 8003

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8003", "app:app"]
