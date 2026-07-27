# Fokus — EdTech Platformasi (MVP v0)

Onlayn ta'lim platformasi: jonli video darslar (LiveKit), avtomatik davomat va
rozilikka asoslangan ota-ona paneli. O'zbekiston bozori uchun.

> Arxitektura qoidalari: [ARCHITECTURE.md](ARCHITECTURE.md) — yangi kod yozishdan oldin o'qing.

## Stack

- **Backend:** Django + DRF + SimpleJWT (`root/` — settings, `apps/` — modullar)
- **Video:** LiveKit (self-hosted, docker-compose)
- **DB:** PostgreSQL (dev'da sqlite fallback)
- **Frontend:** React + Vite (`frontend/` — keyingi bosqich)

## Modullar

| Modul | Vazifasi |
|---|---|
| `apps/accounts` | Auth (JWT), 4 rol, ota-ona↔bola bog'lash (taklif-kod + tasdiq), rozilik (consent) |
| `apps/lessons` | Kurs, dars jadvali, yozilish, davomat hisoboti |
| `apps/live` | LiveKit xona tokeni + avtomatik davomat (kirdi/chiqdi) |

## Ishga tushirish

```bash
# 1. Muhit
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env

# 2. Infratuzilma (ixtiyoriy — sqlite bilan ham ishlaydi)
docker compose up -d          # Postgres + Redis + LiveKit

# 3. Migratsiya va server
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API hujjatlari: http://localhost:8000/api/docs/

## Smoke test

To'liq oqim (ro'yxat → bola → taklif-kod → dars → LiveKit token → davomat):

```bash
python scripts/smoke_test.py
```

## Muhim qarorlar

- **Rozilik-modeli:** ota-ona bolani faqat bolaning taklif-kodi va tasdig'i bilan
  kuzatadi; bola istalgan payt uzadi (prototipdagi Tahlil oqimi).
- **Self-hosted LiveKit:** birlik iqtisodi + data localization talabi
  (Tanqidiy Tahlil v4, 5- va 7-bo'limlar).
- **Migratsiyalar git'da yo'q:** har muhitda `makemigrations` qilinadi.
