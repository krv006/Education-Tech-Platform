FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg — dars yozuvining video (Track Egress) va audio (brauzerdan
# chunked upload) qismlarini birlashtirish uchun (-c copy, qayta kodlashsiz).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "root.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
