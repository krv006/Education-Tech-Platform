FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg — brauzerdan (chunked upload) kelgan video+audio yozuvlarini
# birlashtirish uchun (-c copy, qayta kodlashsiz). mkvtoolnix (mkvmerge) —
# tarmoq uzilib-ulanganda ko'p segmentga bo'lingan WebM fayllarni QAYTA
# KODLAMASDAN (CPU tejash rejasiga mos) to'g'irlash uchun.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg mkvtoolnix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "root.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
