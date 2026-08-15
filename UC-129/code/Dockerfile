# Codificando.AI - UC-129
# Imagen del API Flask del sistema de métricas de resiliencia LLMOps.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    APP_PORT=8002

EXPOSE 8002

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8002", "app:app"]
