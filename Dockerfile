FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOOKING_DB_PATH=/data/bookings.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web

RUN useradd --create-home --uid 10001 auren \
    && mkdir -p /data \
    && chown -R auren:auren /app /data
USER auren

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
