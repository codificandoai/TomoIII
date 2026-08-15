# Codificando.AI - UC-127
# Imagen del API Flask que expone el orquestador de respuesta a incidentes.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    APP_PORT=8001

EXPOSE 8001

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8001", "app:app"]
